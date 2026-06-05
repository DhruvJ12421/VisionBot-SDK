import subprocess
import cv2
import numpy as np
import time
import threading
import re
from typing import Optional, Tuple, Union

class AndroidDevice:
    """
    Core controller representing a physical Android device or emulator connected via ADB.
    Provides non-blocking, thread-safe screen streaming and fast input execution.
    """

    def __init__(self, device_id: Optional[str] = None, capture_fps: int = 15, downscale_factor: float = 1.0):
        self.device_id = device_id
        self.capture_fps = capture_fps
        self.downscale_factor = downscale_factor
        
        # Verify ADB is installed and get connected devices if not specified
        self._verify_adb()
        if not self.device_id:
            self.device_id = self._autodetect_device()
            
        print(f"[Device] Connected to Android Device: {self.device_id}")

        # Get actual screen resolution
        self.width, self.height = self._get_screen_resolution()
        print(f"[Device] Detected Screen Resolution: {self.width}x{self.height}")

        # Screen capture frame buffer
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._stop_capture = threading.Event()
        self._capture_thread = None

        # Input injection interfaces
        self._monkey_input = None
        
        # Start capture thread
        self.start_capture()

    def _verify_adb(self):
        try:
            subprocess.run(["adb", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            raise RuntimeError("[Device] ADB (Android Debug Bridge) is not installed or not in your system PATH.")

    def _autodetect_device(self) -> str:
        proc = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, text=True, check=True)
        lines = proc.stdout.strip().split("\n")[1:]
        devices = [line.split("\t")[0] for line in lines if line.strip() and "\tdevice" in line]
        
        if not devices:
            raise RuntimeError("[Device] No ADB devices or emulators attached. Please connect a device or start an emulator.")
        return devices[0]

    def _get_screen_resolution(self) -> Tuple[int, int]:
        output = self.shell("wm size")
        match = re.search(r"(\d+)x(\d+)", output)
        if match:
            return int(match.group(1)), int(match.group(2))
        # Default fallback
        return 1920, 1080

    def adb_cmd_prefix(self) -> list:
        if self.device_id:
            return ["adb", "-s", self.device_id]
        return ["adb"]

    def shell(self, cmd: str) -> str:
        """Executes a command inside the Android device shell and returns standard output."""
        full_cmd = self.adb_cmd_prefix() + ["shell", cmd]
        proc = subprocess.run(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            return proc.stdout.strip()
        return proc.stdout.strip()

    # ==========================================
    # BACKGROUND FRAME STREAMING (THREAD-SAFE)
    # ==========================================

    def start_capture(self):
        """Starts the background non-blocking screencap loop thread."""
        if self._capture_thread and self._capture_thread.is_alive():
            return
            
        self._stop_capture.clear()
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        # Wait until the first frame is captured
        start_time = time.time()
        while self.get_frame() is None:
            if time.time() - start_time > 5.0:
                raise TimeoutError("[Device] Timeout waiting for initial screen capture frame.")
            time.sleep(0.05)

    def stop_capture(self):
        """Stops the background screen capture thread."""
        if hasattr(self, '_stop_capture'):
            self._stop_capture.set()
        if hasattr(self, '_capture_thread') and self._capture_thread:
            self._capture_thread.join(timeout=2.0)


    def _capture_loop(self):
        interval = 1.0 / self.capture_fps
        cmd = self.adb_cmd_prefix() + ["exec-out", "screencap", "-p"]

        while not self._stop_capture.is_set():
            loop_start = time.time()
            
            try:
                # exec-out is binary-safe on Windows and avoids standard stdout CRLF issues
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                raw_bytes = proc.stdout.read()
                proc.wait()
                
                if not raw_bytes:
                    continue
                    
                img_np = np.frombuffer(raw_bytes, np.uint8)
                frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

                if frame is not None:
                    # Apply downscaling for faster CV processing
                    if self.downscale_factor != 1.0:
                        frame = cv2.resize(
                            frame, None, 
                            fx=self.downscale_factor, 
                            fy=self.downscale_factor, 
                            interpolation=cv2.INTER_AREA
                        )
                    
                    with self._frame_lock:
                        self._latest_frame = frame
            except Exception as e:
                print(f"[Device] Screencap streaming error: {e}")
                
            # Maintain target FPS
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, interval - elapsed)
            time.sleep(sleep_time)

    def get_frame(self) -> Optional[np.ndarray]:
        """Returns a copy of the latest captured screen frame, or None if not ready."""
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    # ==========================================
    # INPUT INJECTION
    # ==========================================

    def set_monkey_input(self, monkey_client):
        """Registers a FastInput socket client to handle taps/swipes instantaneously."""
        self._monkey_input = monkey_client

    def _scale_coordinates(self, x: Union[int, float], y: Union[int, float]) -> Tuple[int, int]:
        """Converts float coordinates (0.0 to 1.0) into absolute pixel coordinates."""
        abs_x = int(x * self.width) if isinstance(x, float) else x
        abs_y = int(y * self.height) if isinstance(y, float) else y
        return abs_x, abs_y

    def tap(self, x: Union[int, float], y: Union[int, float]):
        """Injects a tap event. Supports absolute pixels or normalized floats (0.0 - 1.0)."""
        abs_x, abs_y = self._scale_coordinates(x, y)
        
        # Use low-latency Monkey injection if active, otherwise fallback to standard shell tap
        if self._monkey_input:
            self._monkey_input.tap(abs_x, abs_y)
        else:
            self.shell(f"input tap {abs_x} {abs_y}")

    def swipe(self, x1: Union[int, float], y1: Union[int, float], x2: Union[int, float], y2: Union[int, float], duration_ms: int = 300):
        """Injects a swipe/drag event. Supports absolute pixels or normalized floats."""
        abs_x1, abs_y1 = self._scale_coordinates(x1, y1)
        abs_x2, abs_y2 = self._scale_coordinates(x2, y2)
        
        if self._monkey_input:
            self._monkey_input.swipe(abs_x1, abs_y1, abs_x2, abs_y2, duration_ms)
        else:
            self.shell(f"input swipe {abs_x1} {abs_y1} {abs_x2} {abs_y2} {duration_ms}")

    def __del__(self):
        self.stop_capture()
