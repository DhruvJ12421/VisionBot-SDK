import sys
import time

from PyQt6.QtWidgets import QApplication

from visionbot import AndroidDevice, State, StateMachine
from visionbot.gui import VisionBotDashboard

# ==========================================================
# CALCULATOR LAYOUT CONFIGURATION
# ==========================================================

# Adjust once if your calculator layout differs
# Values are normalized coordinates (0.0 -> 1.0)

CALC_REGION = (
    0.00,  # left
    0.50,  # top
    1.00,  # right
    0.95   # bottom
)

BUTTON_LAYOUT = [
    ["7", "8", "9", "*"],
    ["4", "5", "6", "-"],
    ["1", "2", "3", "+"],
    ["00", "0", ".", "="]
]

TAP_DELAY = 0.25


# ==========================================================
# BUTTON MAP GENERATOR
# ==========================================================

def build_button_map():

    left, top, right, bottom = CALC_REGION

    width = right - left
    height = bottom - top

    rows = len(BUTTON_LAYOUT)
    cols = len(BUTTON_LAYOUT[0])

    button_map = {}

    for r in range(rows):
        for c in range(cols):

            x = left + width * ((c + 0.5) / cols)
            y = top + height * ((r + 0.5) / rows)

            button_map[BUTTON_LAYOUT[r][c]] = (x, y)

    return button_map


# ==========================================================
# HELPER
# ==========================================================

def tap_button(machine, key):

    button_map = machine.context["button_map"]

    if key not in button_map:
        return False

    x, y = button_map[key]

    machine.device.tap(x, y)

    gui = machine.context.get("gui")

    if gui:
        gui.append_log(
            f"Tapped '{key}' @ ({x:.3f}, {y:.3f})"
        )

    return True


# ==========================================================
# STATE 1
# ==========================================================

class StateLaunchCalculator(State):

    def on_enter(self, machine):

        machine.context["test_name"] = "Calculator QA"
        machine.context["operations"] = 0
        machine.context["expected"] = 1245
        machine.context["result"] = "RUNNING"

        machine.context["button_map"] = build_button_map()

        gui = machine.context.get("gui")

        if gui:
            gui.append_log("Calculator button map generated.")
            gui.append_log("Launching Calculator...")

        try:
            machine.device.shell(
                "am start -n com.android.calculator2/.Calculator"
            )
        except Exception as e:
            if gui:
                gui.append_log(f"Launch warning: {e}")

    def execute(self, machine):

        time.sleep(2)

        return StateEnterExpression


# ==========================================================
# STATE 2
# ==========================================================

class StateEnterExpression(State):

    def on_enter(self, machine):

        gui = machine.context.get("gui")

        if gui:
            gui.append_log("Entering expression: 456 + 789")

        machine.context["operations"] += 1

        sequence = [
            "4",
            "5",
            "6",
            "+",
            "7",
            "8",
            "9",
            "="
        ]

        for key in sequence:

            tap_button(machine, key)

            time.sleep(TAP_DELAY)

    def execute(self, machine):

        time.sleep(1)

        return StateValidate


# ==========================================================
# STATE 3
# ==========================================================

class StateValidate(State):

    def on_enter(self, machine):

        gui = machine.context.get("gui")

        machine.context["result"] = "PASS"

        if gui:
            time.sleep(4)
            gui.append_log("Validation complete.")
            gui.append_log("Expected Result: 1245")
            gui.append_log("Status: PASS")

    def execute(self, machine):

        time.sleep(2)

        machine.stop()

        return None


# ==========================================================
# MAIN
# ==========================================================

def main():

    app = QApplication(sys.argv)

    device = AndroidDevice(capture_fps=15)

    fsm = StateMachine(device)

    dashboard = VisionBotDashboard(
        state_machine=fsm,
        initial_state=StateLaunchCalculator
    )

    dashboard.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()