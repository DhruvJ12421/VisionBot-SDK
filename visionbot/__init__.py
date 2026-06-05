from .device import AndroidDevice
from .vision import TemplateMatcher
from .fsm import StateMachine, State

# Optional GUI export to allow CLI-only execution without PyQt6 installed
try:
    from .gui import VisionBotDashboard
    _has_gui = True
except ImportError:
    _has_gui = False

__all__ = [
    "AndroidDevice",
    "TemplateMatcher",
    "StateMachine",
    "State",
]

if _has_gui:
    __all__.append("VisionBotDashboard")
