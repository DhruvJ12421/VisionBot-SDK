import subprocess
import socket
import time
from typing import Optional

class FastInput:
    """
    High-speed touch injection using the Android Monkey protocol over a TCP socket.
    Reduces tap dispatch latency from 350ms (adb shell input tap) to under 1ms.
    """

    def __init__(self, device, port: int = 1080):
        self.device = device
        self.port = port
        self.socket: Optional[socket.socket] = None
        
        # Start the Monkey server and connect
        self._initialize_monkey()

    def _initialize_monkey(self):
        # 1. Forward TCP port from local machine to device
        forward_cmd = self.device.adb_cmd_prefix() + ["forward", f"tcp:{self.port}", f"tcp:{self.port}"]
        subprocess.run(forward_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Check if monkey is already running, otherwise spawn it
        ps_output = self.device.shell("ps -A")
        if "com.android.commands.monkey" not in ps_output and "monkey" not in ps_output:
            # Start monkey server in background
            monkey_cmd = self.device.adb_cmd_prefix() + ["shell", "monkey", "--port", str(self.port), "--type", "usb"]
            subprocess.Popen(monkey_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Give the server a moment to start
            time.sleep(0.5)

        # 3. Connect socket with retry mechanism
        for attempt in range(5):
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect(("127.0.0.1", self.port))
                self.socket.settimeout(1.0)
                
                # Tell the AndroidDevice instance to use this fast input
                self.device.set_monkey_input(self)
                return
            except ConnectionRefusedError:
                time.sleep(0.2)
                
        raise RuntimeError(
            f"[FastInput] Failed to connect to Android Monkey server on port {self.port}. "
            "Please check if the port is busy or ADB connection is active."
        )

    def tap(self, x: int, y: int):
        """Dispatches an instantaneous click event at the absolute pixel coordinate."""
        if not self.socket:
            raise RuntimeError("[FastInput] FastInput socket is not connected.")
        try:
            self.socket.sendall(f"tap {x} {y}\n".encode())
            # Monkey returns an OK status line which we should read to clear buffer
            self.socket.recv(128)
        except Exception:
            pass

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """Simulates a drag event via rapid down/move/up events."""
        if not self.socket:
            raise RuntimeError("[FastInput] FastInput socket is not connected.")
        try:
            # Start touch down
            self.socket.sendall(f"touch down {x1} {y1}\n".encode())
            self.socket.recv(128)
            
            # Simple linear move steps (for natural swipe response)
            steps = 5
            for i in range(1, steps + 1):
                t = i / steps
                curr_x = int(x1 + (x2 - x1) * t)
                curr_y = int(y1 + (y2 - y1) * t)
                self.socket.sendall(f"touch move {curr_x} {curr_y}\n".encode())
                self.socket.recv(128)
                time.sleep((duration_ms / steps) / 1000.0)
                
            # Finish touch up
            self.socket.sendall(f"touch up {x2} {y2}\n".encode())
            self.socket.recv(128)
        except Exception:
            pass

    def close(self):
        """Closes the socket connection and stops port forwarding."""
        if self.socket:
            self.socket.close()
            self.socket = None
            self.device.set_monkey_input(None)

        # Clear port forwarding
        clear_cmd = self.device.adb_cmd_prefix() + ["forward", "--remove", f"tcp:{self.port}"]
        subprocess.run(clear_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def __del__(self):
        self.close()
