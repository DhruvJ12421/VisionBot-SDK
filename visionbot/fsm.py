import time
from typing import Dict, Any, Optional, Type, Union

class State:
    """
    Base class representing a single state in the automation lifecycle.
    Custom bot behaviors must subclass this and implement the execute() method.
    """
    
    def on_enter(self, machine: 'StateMachine'):
        """Executed once when transitioning into this state."""
        pass

    def execute(self, machine: 'StateMachine') -> Optional[Union[str, Type['State'], 'State']]:
        """
        Executed continuously inside the state machine loop.
        Returns the next State (instance, class, or registered name) to transition to, 
        or None to remain in this state.
        """
        raise NotImplementedError("[State] States must implement the execute() lifecycle hook.")

    def on_exit(self, machine: 'StateMachine'):
        """Executed once when transitioning out of this state."""
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__


class StateMachine:
    """
    Manager that controls state transitions, global variables context, and the execution loop.
    Acts as the orchestrator for the entire automation script.
    """

    def __init__(self, device):
        self.device = device
        self.context: Dict[str, Any] = {}
        self.states: Dict[str, State] = {}
        self.current_state: Optional[State] = None
        self._running: bool = False
        self.on_state_change = None  # Optional callback function: fn(old_state_name, new_state_name)

    def register(self, state: State):
        """Registers a state instance in the machine registry."""
        self.states[state.name] = state
        self.states[state.__class__] = state

    def start(self, initial_state: Union[State, Type[State], str]):
        """Sets the initial state and runs its on_enter lifecycle hook."""
        self.current_state = self._resolve_state(initial_state)
        if not self.current_state:
            raise ValueError(f"[StateMachine] Initial state could not be resolved: {initial_state}")
            
        print(f"[StateMachine] Starting State Machine in: {self.current_state.name}")
        self.current_state.on_enter(self)
        self._running = True
        
        if self.on_state_change:
            self.on_state_change(None, self.current_state.name)

    def step(self):
        """Executes a single iteration of the current state and handles any transition."""
        if not self._running or not self.current_state:
            return

        # Execute current state logic and check for transition
        next_state_raw = self.current_state.execute(self)
        
        if next_state_raw is not None:
            next_state = self._resolve_state(next_state_raw)
            if next_state and next_state != self.current_state:
                print(f"[StateMachine] Transitioning: {self.current_state.name} -> {next_state.name}")
                
                # Execute transition lifecycles
                self.current_state.on_exit(self)
                old_state = self.current_state
                self.current_state = next_state
                self.current_state.on_enter(self)
                
                if self.on_state_change:
                    self.on_state_change(old_state.name, next_state.name)

    def run(self, tick_rate_seconds: float = 0.05):
        """Blocking loop that executes state steps continuously at the specified tick rate."""
        try:
            while self._running:
                loop_start = time.time()
                self.step()
                elapsed = time.time() - loop_start
                sleep_time = max(0.0, tick_rate_seconds - elapsed)
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            print("\n[StateMachine] State Machine stopped manually by user.")
            self.stop()

    def stop(self):
        """Stops the state machine execution loop."""
        self._running = False
        if self.current_state:
            self.current_state.on_exit(self)
            self.current_state = None

    def _resolve_state(self, state_ref: Union[State, Type[State], str]) -> Optional[State]:
        """Helper to resolve a state reference to a registered State instance."""
        if isinstance(state_ref, State):
            if state_ref.name not in self.states:
                self.register(state_ref)
            return state_ref
            
        if isinstance(state_ref, str):
            return self.states.get(state_ref)
            
        if issubclass(state_ref, State):
            if state_ref not in self.states:
                instance = state_ref()
                self.register(instance)
            return self.states.get(state_ref)
            
        return None
