# 🤖 VisionBot-SDK: Real-Time Mobile Automation Framework

**VisionBot-SDK** is a high-performance, developer-first Android automation engine in Python. It provides a lightweight, robust, and zero-bloat alternative to heavier mobile testing platforms like Appium.

## 🚀 Key Advantages
* **⚡ <1ms Input Latency:** Directly injects taps and swipes over an Android Monkey socket, bypassing the 300ms Java VM overhead of standard `input tap`.
* **📸 Non-Blocking Screencapping:** Background thread-safe frame streaming decodes device frames continuously into an active buffer using binary-safe pipes.
* **📐 Bounding-Box Coordinate Autoscale:** Normalizes screen layout coordinates from `0.0` to `1.0`. The SDK automatically scales actions to match the actual display resolution.
* **🧠 Extensible State Machine:** Replaces spaghetti code loops and fragile `time.sleep()` statements with an event-driven Finite State Machine (FSM) framework.
* **🖥️ Reusable Visual Dashboard:** An optional, dark-themed GUI submodule (`visionbot.gui.VisionBotDashboard`) that dynamically renders live viewports, sliders, and telemetry statistics.

---

## 🛠️ Getting Started

### 1. Prerequisites
* **Python 3.8+**
* **ADB (Android Debug Bridge)** installed and added to your system `PATH`.
* A connected Android device or emulator (verify with `adb devices`).

### 2. Installation
Install the required packages in your local environment:
```bash
pip install -r requirements.txt
```

---

## 💻 Quick Start Example

This code demonstrates how to connect to a device, stream the screen at 15 FPS, check for visual elements, and trigger clicks with absolute ease.

```python
from visionbot import AndroidDevice, TemplateMatcher
from visionbot.input import FastInput
import time

# 1. Automatically connect to the active device/emulator
device = AndroidDevice(capture_fps=15, downscale_factor=1.0)

# 2. Start high-speed low-latency touch client (Port 1080)
fast_input = FastInput(device)

# 3. Initialize CV Template Matcher
play_btn = TemplateMatcher("templates/play_button.png")

print("Waiting for Play button to appear on screen...")
while True:
    frame = device.get_frame()
    if frame is not None:
        # Search for the button with 85% confidence threshold
        match = play_btn.match(frame, threshold=0.85)
        if match:
            x, y = match
            print(f"Play button found at pixel: {x}, {y}. Tapping!")
            device.tap(x, y)
            break
            
    time.sleep(0.05)
```

---

## 🌀 Building Robust Bots with the State Machine (FSM)

The recommended pattern is to structure your automations into modular `State` classes. Each state performs one action and routes to the next state based on real-time screen assessments.

### Example FSM Design

```python
import time
from visionbot import State, StateMachine, AndroidDevice
from visionbot.vision import get_color_ratio

LOW_CYAN, UP_CYAN = (80, 60, 160), (110, 255, 255)

class StateExploring(State):
    def on_enter(self, machine):
        print("Walking to trigger encounter...")
        machine.device.tap(0.94, 0.46) # Auto-scales normalized float coordinate!

    def execute(self, machine):
        frame = machine.device.get_frame()
        if frame is not None:
            # Check for battle Run button (crop box on left side of screen)
            cyan_ratio = get_color_ratio(frame, LOW_CYAN, UP_CYAN, region=(0.05, 0.1, 0.15, 0.25))
            if cyan_ratio > 0.08:
                return StateInBattle
        return None

class StateInBattle(State):
    def on_enter(self, machine):
        print("In Battle! Transitioning to action...")
        machine.stop() # Stops execution loop

# Run FSM Orchestrator
device = AndroidDevice()
fsm = StateMachine(device)

fsm.register(StateExploring())
fsm.register(StateInBattle())

fsm.start(StateExploring)
fsm.run(tick_rate_seconds=0.05)
```

For full battle-ready examples, check out:
* **[examples/encounter_bot.py](file:///c:/Users/Dhruv%20Jain/Downloads/Tools/AutomationBot/examples/encounter_bot.py)** (Console version)
* **[examples/encounter_bot_gui.py](file:///c:/Users/Dhruv%20Jain/Downloads/Tools/AutomationBot/examples/encounter_bot_gui.py)** (Visual GUI version utilizing the generic dashboard module)
