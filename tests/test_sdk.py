import unittest
import numpy as np
import sys
import os

# Ensure package is discoverable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from visionbot import AndroidDevice, TemplateMatcher, StateMachine, State
from visionbot.fsm import State as FsmState

class DummyDevice:
    """Mock device for testing."""
    def __init__(self):
        self.width = 1920
        self.height = 1080
        self.monkey_input = None

    def set_monkey_input(self, client):
        self.monkey_input = client

    def _scale_coordinates(self, x, y):
        abs_x = int(x * self.width) if isinstance(x, float) else x
        abs_y = int(y * self.height) if isinstance(y, float) else y
        return abs_x, abs_y

class TestSDKCore(unittest.TestCase):
    
    def test_imports(self):
        """Verifies all main library classes are importable from the root package."""
        self.assertIsNotNone(AndroidDevice)
        self.assertIsNotNone(TemplateMatcher)
        self.assertIsNotNone(StateMachine)
        self.assertIsNotNone(State)

    def test_coordinate_scaling(self):
        """Tests that normalized coordinates correctly scale to screen resolution absolute pixels."""
        device = DummyDevice()
        
        # Test floats
        ax, ay = device._scale_coordinates(0.5, 0.25)
        self.assertEqual(ax, 960)
        self.assertEqual(ay, 270)
        
        # Test absolute ints
        ax, ay = device._scale_coordinates(100, 200)
        self.assertEqual(ax, 100)
        self.assertEqual(ay, 200)

    def test_fsm_execution(self):
        """Tests Finite State Machine transitions and context handling."""
        
        class StateA(FsmState):
            def execute(self, machine):
                machine.context["visited_a"] = True
                return StateB

        class StateB(FsmState):
            def execute(self, machine):
                machine.context["visited_b"] = True
                machine.stop()
                return None

        # Setup FSM
        device = DummyDevice()
        fsm = StateMachine(device)
        fsm.context["visited_a"] = False
        fsm.context["visited_b"] = False

        # Register and run
        fsm.register(StateA())
        fsm.register(StateB())
        
        fsm.start(StateA)
        self.assertTrue(fsm._running)
        self.assertEqual(fsm.current_state.name, "StateA")
        
        # Step once (StateA -> StateB)
        fsm.step()
        self.assertTrue(fsm.context["visited_a"])
        self.assertEqual(fsm.current_state.name, "StateB")
        
        # Step again (StateB execution)
        fsm.step()
        self.assertTrue(fsm.context["visited_b"])
        self.assertFalse(fsm._running)
        self.assertIsNone(fsm.current_state)

if __name__ == "__main__":
    unittest.main()
