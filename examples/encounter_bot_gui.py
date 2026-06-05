import sys
import os
import time
import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication, QMessageBox

# Ensure visionbot package is discoverable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# VisionBot SDK Imports
from visionbot import StateMachine, State, AndroidDevice, VisionBotDashboard
from visionbot.input import FastInput
from visionbot.vision import get_color_ratio, get_multi_color_ratio

# ==========================================
# CONFIGURATION
# ==========================================

RARITY_REGION = (0.93, 0.06, 0.97, 0.12)
LOW_CYAN, UP_CYAN = (80, 60, 160), (110, 255, 255)
RED_RANGES = [
    ((0, 120, 70), (10, 255, 255)),
    ((170, 120, 70), (180, 255, 255))
]

# Coordinate points (absolute or normalized floats)
MOVE_PT = (3020, 500)
RUN_PT = (280, 310)
CONFIRM_PT = (1890, 980)
DISMISS_PT = (1890, 1080)

# ==========================================
# GAME-SPECIFIC AUTOMATION STATES
# ==========================================

class StateExploring(State):
    """Overworld exploring state. Taps movement coordinate and walks."""

    def on_enter(self, machine: StateMachine):
        machine.context["gui"].append_log("Exploring overworld... Triggering encounter.")
        machine.device.tap(*MOVE_PT)
        machine.context["move_time"] = time.time()

    def execute(self, machine: StateMachine):
        frame = machine.device.get_frame()
        if frame is None:
            return None

        # Check run button cyan ratio
        run_region = (0.05, 0.10, 0.15, 0.25)
        cyan_ratio = get_color_ratio(frame, LOW_CYAN, UP_CYAN, region=run_region)

        if cyan_ratio > 0.08:
            return StateCheckingRarity

        # Walk timeout
        if time.time() - machine.context.get("move_time", 0) > 8.0:
            machine.device.tap(*MOVE_PT)
            machine.context["move_time"] = time.time()

        return None


class StateCheckingRarity(State):
    """Encounter screen active. Evaluates if the monster is Ultra Rare."""

    def on_enter(self, machine: StateMachine):
        machine.context["check_start"] = time.time()

    def execute(self, machine: StateMachine):
        frame = machine.device.get_frame()
        if frame is None:
            return None

        # Calculate red ratio in cropped badge
        score = get_multi_color_ratio(frame, RED_RANGES, region=RARITY_REGION)
        
        # Read dynamic threshold slider value from FSM context
        threshold = machine.context.get("ur_threshold", 0.03)

        if score >= threshold:
            return StateURFound

        if time.time() - machine.context["check_start"] > 1.8:
            return StateRunningAway

        return None


class StateRunningAway(State):
    """Handles running away from a common monster and dismissing standard popups."""

    def on_enter(self, machine: StateMachine):
        # Tap the escape/run buttons
        machine.device.tap(*RUN_PT)
        time.sleep(0.4)
        machine.device.tap(*CONFIRM_PT)
        
        # Increment dynamic counter inside fsm.context
        machine.context["encounters"] = machine.context.get("encounters", 0) + 1
        machine.context["run_start"] = time.time()

    def execute(self, machine: StateMachine):
        elapsed = time.time() - machine.context["run_start"]
        if elapsed > 1.5 and elapsed < 1.7:
            machine.device.tap(*DISMISS_PT)
            
        if elapsed >= 3.0:
            return StateExploring
            
        return None


class StateURFound(State):
    """UR found. Stops FSM loop and alerts user via GUI popup."""

    def on_enter(self, machine: StateMachine):
        machine.context["gui"].append_log("Alert! Ultra Rare encounter active. Automation suspended.")
        machine.stop()
        
        # Show a GUI dialog box (safely running in the UI thread via parent caller)
        QMessageBox.information(
            None, "🌟 Ultra Rare Found!", 
            "The bot has detected an Ultra Rare monster and suspended operations!\nPlease complete the capture manually.",
            QMessageBox.StandardButton.Ok
        )

    def execute(self, machine: StateMachine):
        return None


# ==========================================
# SIMULATION / SANDBOX DUMMY DEVICE
# ==========================================

class MockDevice:
    """Mock Android device generating visual frames in sandbox mode."""
    def __init__(self):
        self.width = 1920
        self.height = 1080
        self.state_ticks = 0
        self.simulated_state = "exploring"
        self._frame = self._draw_exploring()

    def get_frame(self) -> np.ndarray:
        self.state_ticks += 1
        # Loop dummy transitions
        if self.simulated_state == "exploring" and self.state_ticks > 50:
            self.simulated_state = "checking"
            self.state_ticks = 0
        elif self.simulated_state == "checking" and self.state_ticks > 25:
            # 20% chance to simulate finding UR
            self.simulated_state = "ur_found" if np.random.rand() < 0.20 else "escape"
            self.state_ticks = 0
        elif self.simulated_state == "escape" and self.state_ticks > 40:
            self.simulated_state = "exploring"
            self.state_ticks = 0

        # Draw frame
        if self.simulated_state == "exploring":
            self._frame = self._draw_exploring()
        elif self.simulated_state == "checking":
            self._frame = self._draw_battle(has_ur=False)
        elif self.simulated_state == "ur_found":
            self._frame = self._draw_battle(has_ur=True)
        elif self.simulated_state == "escape":
            self._frame = self._draw_escape()

        return self._frame.copy()

    def tap(self, x, y): pass
    def swipe(self, x1, y1, x2, y2, duration=300): pass

    def _draw_exploring(self) -> np.ndarray:
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        img[:, :] = (35, 120, 35) # Grass
        cv2.circle(img, (960, 540), 40, (0, 0, 255), -1) # Player
        cv2.putText(img, "OVERWORLD (Walking...)", (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 4)
        cv2.putText(img, "Sandbox Simulation Active", (100, 180), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
        return img

    def _draw_battle(self, has_ur: bool = False) -> np.ndarray:
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        img[0:720, :] = (230, 180, 140) # Sky
        img[720:, :] = (50, 180, 50) # Ground
        
        # Cyan Run Button
        cv2.rectangle(img, (100, 120), (280, 260), (220, 220, 80), -1)
        cv2.putText(img, "RUN", (150, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        # Rarity Badge
        if has_ur:
            cv2.rectangle(img, (1780, 60), (1870, 130), (0, 0, 255), -1) # Red BGR
            cv2.putText(img, "UR", (1805, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
            cv2.putText(img, "ULTRA RARE ENCOUNTER!", (500, 450), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
        else:
            cv2.rectangle(img, (1780, 60), (1870, 130), (120, 120, 120), -1) # Grey BGR
            cv2.putText(img, "N", (1810, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
            cv2.putText(img, "Common Encounter", (600, 450), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 4)
        return img

    def _draw_escape(self) -> np.ndarray:
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        img[:, :] = (80, 80, 80)
        cv2.putText(img, "RUNNING AWAY...", (600, 500), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 5)
        return img


class MockFastInput:
    def tap(self, x, y): pass
    def swipe(self, x1, y1, x2, y2, duration=300): pass
    def close(self): pass


# ==========================================
# MAIN EXECUTION ENTRY
# ==========================================

if __name__ == "__main__":
    sandbox = "--demo" in sys.argv or "--sandbox" in sys.argv
    
    app = QApplication(sys.argv)
    
    # 1. Initialize Device Link
    if sandbox:
        device = MockDevice()
        fast_input = MockFastInput()
    else:
        try:
            device = AndroidDevice(capture_fps=15, downscale_factor=1.0)
            fast_input = FastInput(device)
        except Exception as e:
            # Confirm sandbox fallback if no USB device connected
            print(f"[Main] USB Device connection failed: {e}")
            reply = QMessageBox.question(
                None, "No Device Detected",
                "No physical Android device/emulator was detected over ADB.\n\nWould you like to run in Sandbox Simulation mode?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                sandbox = True
                device = MockDevice()
                fast_input = MockFastInput()
            else:
                sys.exit(1)

    # 2. Build the state machine
    bot_fsm = StateMachine(device)
    bot_fsm.context["encounters"] = 0
    bot_fsm.context["ur_threshold"] = 0.03

    bot_fsm.register(StateExploring())
    bot_fsm.register(StateCheckingRarity())
    bot_fsm.register(StateRunningAway())
    bot_fsm.register(StateURFound())

    # 3. Instantiate and run the universal Visual Dashboard from the library!
    win = VisionBotDashboard(bot_fsm, initial_state=StateExploring, sandbox_mode=sandbox)
    win.show()
    
    sys.exit(app.exec())
