import time
import sys
import os

# Ensure package is discoverable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from visionbot import AndroidDevice, StateMachine, State
from visionbot.input import FastInput
from visionbot.vision import get_color_ratio, get_multi_color_ratio

# ==========================================
# CONFIGURATION
# ==========================================

RARITY_REGION = (0.93, 0.06, 0.97, 0.12)
UR_THRESHOLD = 0.03
LOW_CYAN, UP_CYAN = (80, 60, 160), (110, 255, 255)
RED_RANGES = [
    ((0, 120, 70), (10, 255, 255)),
    ((170, 120, 70), (180, 255, 255))
]

MOVE_PT = (3020, 500)
RUN_PT = (280, 310)
CONFIRM_PT = (1890, 980)
DISMISS_PT = (1890, 1080)

# ==========================================
# STATE MACHINE DEFINITIONS
# ==========================================

class StateExploring(State):
    def on_enter(self, machine: StateMachine):
        print("[Exploring] Exploring overworld... Triggering encounter.")
        machine.device.tap(*MOVE_PT)
        machine.context["move_time"] = time.time()

    def execute(self, machine: StateMachine):
        frame = machine.device.get_frame()
        if frame is None:
            return None

        run_region = (0.05, 0.10, 0.15, 0.25)
        cyan_ratio = get_color_ratio(frame, LOW_CYAN, UP_CYAN, region=run_region)

        if cyan_ratio > 0.08:
            print("[Exploring] Encounter detected!")
            return StateCheckingRarity

        if time.time() - machine.context.get("move_time", 0) > 8.0:
            machine.device.tap(*MOVE_PT)
            machine.context["move_time"] = time.time()
        return None


class StateCheckingRarity(State):
    def on_enter(self, machine: StateMachine):
        print("[RarityCheck] Checking monster rarity badge...")
        machine.context["check_start"] = time.time()

    def execute(self, machine: StateMachine):
        frame = machine.device.get_frame()
        if frame is None:
            return None

        score = get_multi_color_ratio(frame, RED_RANGES, region=RARITY_REGION)
        threshold = machine.context.get("ur_threshold", UR_THRESHOLD)

        if score >= threshold:
            print(f"[RarityCheck] ULTRA RARE DETECTED! (Red Score: {score:.4f})")
            return StateURFound

        if time.time() - machine.context["check_start"] > 1.8:
            print(f"[RarityCheck] Common monster found (Red Score: {score:.4f})")
            return StateRunningAway
        return None


class StateRunningAway(State):
    def on_enter(self, machine: StateMachine):
        print("[RunningAway] Initiating escape...")
        machine.device.tap(*RUN_PT)
        time.sleep(0.5)
        machine.device.tap(*CONFIRM_PT)
        
        machine.context["encounters"] = machine.context.get("encounters", 0) + 1
        print(f"[RunningAway] Encounters Checked: {machine.context['encounters']}")
        machine.context["run_start"] = time.time()

    def execute(self, machine: StateMachine):
        elapsed = time.time() - machine.context["run_start"]
        if elapsed > 1.5 and elapsed < 1.7:
            machine.device.tap(*DISMISS_PT)
            
        if elapsed >= 3.0:
            return StateExploring
        return None


class StateURFound(State):
    def on_enter(self, machine: StateMachine):
        print("[URFound] BOT SUSPENDED - Ultra Rare active. Please complete battle manually!")
        machine.stop()

    def execute(self, machine: StateMachine):
        return None


# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    print("[Main] Starting console-based VisionBot Automation Engine...")
    
    device = AndroidDevice(capture_fps=15, downscale_factor=1.0)
    fast_input = FastInput(device)
    
    bot = StateMachine(device)
    bot.context["encounters"] = 0
    bot.context["ur_threshold"] = UR_THRESHOLD
    
    bot.register(StateExploring())
    bot.register(StateCheckingRarity())
    bot.register(StateRunningAway())
    bot.register(StateURFound())
    
    bot.start(StateExploring)
    bot.run(tick_rate_seconds=0.05)
