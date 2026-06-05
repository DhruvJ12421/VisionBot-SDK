import sys
import time
import cv2
import numpy as np
from typing import Optional, Dict, Tuple

# Safe PyQt6 Import
try:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QLabel, QPushButton, 
        QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
        QListWidget, QSlider, QMessageBox
    )
    from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QImage, QPixmap
except ImportError as e:
    raise ImportError("❌ PyQt6 is required to run the GUI. Please run: pip install PyQt6") from e

from visionbot import StateMachine

# ==========================================
# BACKGROUND THREAD FSM WORKER
# ==========================================

class FsmWorker(QThread):
    """Background worker QThread that runs the FSM execution loop so the GUI stays responsive."""
    state_changed = pyqtSignal(str, str) # old_state, new_state
    
    def __init__(self, bot: StateMachine):
        super().__init__()
        self.bot = bot
        self.bot.on_state_change = self._on_transition

    def _on_transition(self, old_state: Optional[str], new_state: str):
        old_name = old_state if old_state else "None"
        self.state_changed.emit(old_name, new_state)

    def run(self):
        # Starts the blocking FSM loop
        self.bot.run(tick_rate_seconds=0.05)

    def stop(self):
        self.bot.stop()
        self.wait()


# ==========================================
# STYLESHEET CONFIGURATION
# ==========================================

DARK_STYLESHEET = """
QMainWindow {
    background-color: #12141a;
}
QWidget {
    color: #e2e8f0;
    font-family: "Segoe UI", Arial, Helvetica;
}
QGroupBox {
    background-color: #1a1d24;
    border: 2px solid #2d3748;
    border-radius: 8px;
    margin-top: 1.5ex;
    font-weight: bold;
    color: #a0aec0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 5px;
}
QPushButton {
    background-color: #3182ce;
    color: white;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
    border: none;
}
QPushButton:hover {
    background-color: #4299e1;
}
QPushButton:pressed {
    background-color: #2b6cb0;
}
QPushButton#stopButton {
    background-color: #e53e3e;
}
QPushButton#stopButton:hover {
    background-color: #fc8181;
}
QPushButton#stopButton:pressed {
    background-color: #c53030;
}
QListWidget {
    background-color: #0f1115;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 5px;
    color: #cbd5e0;
}
QLabel#statusLabel {
    color: #48bb78;
    font-size: 14px;
    font-weight: bold;
}
"""

# ==========================================
# GENERAL-PURPOSE DASHBOARD CLASS
# ==========================================

class VisionBotDashboard(QMainWindow):
    """
    General-purpose visual UI control center for any VisionBot StateMachine.
    Displays live frame captures, transitions, and dynamic FSM context telemetry.
    """

    def __init__(self, state_machine: StateMachine, initial_state = None, sandbox_mode: bool = False):
        super().__init__()
        self.bot_fsm = state_machine
        self.initial_state = initial_state
        self.sandbox_mode = sandbox_mode
        
        # Inject GUI reference into FSM context so states can call: machine.context["gui"].append_log(...)
        self.bot_fsm.context["gui"] = self

        self.setWindowTitle("🤖 VisionBot-SDK Control Center")
        self.resize(1200, 750)
        self.setStyleSheet(DARK_STYLESHEET)

        # Dynamic layout registries
        self.metric_widgets: Dict[str, Tuple[QLabel, QLabel]] = {}
        self.bot_worker: Optional[FsmWorker] = None
        self.fsm_active = False

        # Setup GUI elements
        self._setup_ui()

        # Viewport rendering loop (30 FPS)
        self.feed_timer = QTimer()
        self.feed_timer.timeout.connect(self._update_viewport)
        self.feed_timer.start(33) 

        self.append_log("System UI initialized.")
        if self.sandbox_mode:
            self.append_log("Connection: Running in Sandbox Demo mode.")
        else:
            device_id = getattr(self.bot_fsm.device, 'device_id', 'Unknown')
            self.append_log(f"Connection: Active device link ({device_id})")

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # -------------------------------------------------------------
        # LEFT COLUMN: Live Camera Feed Viewport
        # -------------------------------------------------------------
        left_layout = QVBoxLayout()
        main_layout.addLayout(left_layout, stretch=3)

        feed_group = QGroupBox("LIVE MONITOR FEED")
        feed_vbox = QVBoxLayout(feed_group)
        self.feed_viewport = QLabel()
        self.feed_viewport.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feed_viewport.setStyleSheet("background-color: #000000; border-radius: 4px;")
        self.feed_viewport.setMinimumSize(640, 360)
        feed_vbox.addWidget(self.feed_viewport)
        left_layout.addWidget(feed_group, stretch=1)

        # -------------------------------------------------------------
        # RIGHT COLUMN: Telemetry, Logs, Controls
        # -------------------------------------------------------------
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, stretch=2)

        # 1. System Info
        info_group = QGroupBox("SYSTEM INFORMATION")
        info_grid = QGridLayout(info_group)
        
        info_grid.addWidget(QLabel("Engine Status:"), 0, 0)
        self.status_val = QLabel("IDLE")
        self.status_val.setObjectName("statusLabel")
        self.status_val.setStyleSheet("color: #a0aec0; font-weight: bold;")
        info_grid.addWidget(self.status_val, 0, 1)

        info_grid.addWidget(QLabel("Active State:"), 1, 0)
        self.state_val = QLabel("None")
        self.state_val.setStyleSheet("font-weight: bold; color: #4299e1;")
        info_grid.addWidget(self.state_val, 1, 1)

        info_grid.addWidget(QLabel("Device Connection:"), 2, 0)
        conn_str = "SANDBOX (SIMULATED)" if self.sandbox_mode else f"USB ({getattr(self.bot_fsm.device, 'device_id', 'Active')})"
        self.conn_val = QLabel(conn_str)
        self.conn_val.setStyleSheet("color: #ecc94b;")
        info_grid.addWidget(self.conn_val, 2, 1)

        right_layout.addWidget(info_group)

        # 2. Dynamic Telemetry Context Grid
        self.telemetry_group = QGroupBox("DYNAMIC FSM TELEMETRY")
        self.telemetry_layout = QGridLayout(self.telemetry_group)
        # Add a placeholder label initially
        self.placeholder_label = QLabel("No active telemetry keys found in fsm.context")
        self.placeholder_label.setStyleSheet("color: #718096; font-style: italic;")
        self.telemetry_layout.addWidget(self.placeholder_label, 0, 0)
        right_layout.addWidget(self.telemetry_group)

        # 3. Dynamic Configuration Settings
        config_group = QGroupBox("CONFIGURATION CALIBRATION")
        config_vbox = QVBoxLayout(config_group)

        thresh_hbox = QHBoxLayout()
        thresh_hbox.addWidget(QLabel("Global Param Threshold: "))
        self.thresh_label = QLabel("0.03")
        self.thresh_label.setStyleSheet("font-weight: bold; color: #f56565;")
        thresh_hbox.addWidget(self.thresh_label)
        config_vbox.addLayout(thresh_hbox)

        self.thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self.thresh_slider.setMinimum(1)   # 0.01
        self.thresh_slider.setMaximum(10)  # 0.10
        self.thresh_slider.setValue(3)    # 0.03
        self.thresh_slider.valueChanged.connect(self._on_threshold_changed)
        config_vbox.addWidget(self.thresh_slider)

        right_layout.addWidget(config_group)

        # 4. Logs List Widget
        logs_group = QGroupBox("EVENT LOGGER")
        logs_vbox = QVBoxLayout(logs_group)
        self.log_widget = QListWidget()
        logs_vbox.addWidget(self.log_widget)
        right_layout.addWidget(logs_group, stretch=1)

        # 5. Core FSM controls
        control_hbox = QHBoxLayout()
        self.start_btn = QPushButton("▶ START BOT")
        self.start_btn.clicked.connect(self._on_start)
        control_hbox.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ STOP BOT")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        control_hbox.addWidget(self.stop_btn)

        right_layout.addLayout(control_hbox)

    # ==========================================
    # LOGGING & TELEMETRY INTERNALS
    # ==========================================

    def append_log(self, text: str):
        """Appends a timestamped log to the list widget in a thread-safe style."""
        timestamp = time.strftime("[%H:%M:%S]")
        self.log_widget.addItem(f"{timestamp} {text}")
        self.log_widget.scrollToBottom()

    def _sync_telemetry_metrics(self):
        """Scans context values and dynamically renders labels for any integer/float keys."""
        # Find numeric variables in state_machine.context, ignoring helper keys like "gui"
        ctx = self.bot_fsm.context
        keys = sorted([k for k, v in ctx.items() if k not in ("gui", "check_start", "run_start", "move_time") and isinstance(v, (int, float, str))])

        if keys and self.placeholder_label:
            self.telemetry_layout.removeWidget(self.placeholder_label)
            self.placeholder_label.deleteLater()
            self.placeholder_label = None

        for idx, key in enumerate(keys):
            val = ctx[key]
            
            # Format float nicely
            val_str = f"{val:.4f}" if isinstance(val, float) else str(val)

            if key not in self.metric_widgets:
                # Add new labels dynamically to grid
                lbl_key = QLabel(f"{key.replace('_', ' ').capitalize()}:")
                lbl_val = QLabel(val_str)
                lbl_val.setStyleSheet("font-size: 14px; font-weight: bold; color: #ed8936;")
                
                self.telemetry_layout.addWidget(lbl_key, idx, 0)
                self.telemetry_layout.addWidget(lbl_val, idx, 1)
                self.metric_widgets[key] = (lbl_key, lbl_val)
            else:
                # Update existing text label
                _, lbl_val = self.metric_widgets[key]
                lbl_val.setText(val_str)

    # ==========================================
    # ENGINE RUN CONTROLS
    # ==========================================

    def _on_start(self):
        if self.fsm_active:
            return

        # Inject initial configuration parameter
        float_val = self.thresh_slider.value() / 100.0
        self.bot_fsm.context["ur_threshold"] = float_val
        self.bot_fsm.context["threshold"] = float_val

        # Start FSM dynamically if it hasn't been started yet
        if not self.bot_fsm.current_state and self.initial_state:
            self.bot_fsm.start(self.initial_state)

        # Setup FSM transitions worker QThread
        self.bot_worker = FsmWorker(self.bot_fsm)
        self.bot_worker.state_changed.connect(self._on_state_transition)
        self.bot_worker.start()

        self.fsm_active = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_val.setText("RUNNING")
        self.status_val.setStyleSheet("color: #48bb78; font-weight: bold;")
        self.append_log("StateMachine execution worker thread started.")

    def _on_stop(self):
        if not self.fsm_active or not self.bot_worker:
            return

        self.bot_worker.stop()
        self.bot_worker = None
        
        self.fsm_active = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_val.setText("IDLE")
        self.status_val.setStyleSheet("color: #a0aec0; font-weight: bold;")
        self.state_val.setText("None")
        self.append_log("StateMachine execution worker thread stopped safely.")

    def _on_state_transition(self, old_state: str, new_state: str):
        self.state_val.setText(new_state)
        self.append_log(f"FSM: Transitioned {old_state} -> {new_state}")
        
        # Sync stats grid dynamically on transitions
        self._sync_telemetry_metrics()

        # Stop FSM if final terminal State is reached (i.e. FSM stopped itself)
        if not self.bot_fsm._running:
            self._on_stop()

    def _on_threshold_changed(self, val: int):
        float_val = val / 100.0
        self.thresh_label.setText(f"{float_val:.2f}")
        # Inject updated value directly into FSM context
        self.bot_fsm.context["ur_threshold"] = float_val
        self.bot_fsm.context["threshold"] = float_val
        self.append_log(f"UI: Config slider updated -> {float_val:.2f}")

    # ==========================================
    # VIEWPORT FRAME STREAMING
    # ==========================================

    def _update_viewport(self):
        frame = self.bot_fsm.device.get_frame()
        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            
            q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img).scaled(
                self.feed_viewport.width(), 
                self.feed_viewport.height(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.feed_viewport.setPixmap(pixmap)

    def closeEvent(self, event):
        self.feed_timer.stop()
        if self.fsm_active and self.bot_worker:
            self.bot_worker.stop()
        if hasattr(self.bot_fsm.device, 'close'):
            self.bot_fsm.device.close()
        event.accept()
