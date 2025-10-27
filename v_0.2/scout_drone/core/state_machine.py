"""Mission state management"""
from enum import Enum

class MissionPhase(Enum):
    """Mission phases"""
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    SEARCHING = "SEARCHING"
    TARGET_FOUND = "TARGET_FOUND"
    DELIVERING = "DELIVERING"
    RETURNING = "RETURNING"
    LANDING = "LANDING"
    COMPLETED = "COMPLETED"
    EMERGENCY = "EMERGENCY"

class MissionState:
    """Manages mission state transitions"""
    def __init__(self):
        self.phase = MissionPhase.IDLE
        self.target_position = None
    
    def transition_to(self, new_phase: MissionPhase):
        """Transition to new phase"""
        self.phase = new_phase
    
    def is_active(self) -> bool:
        """Check if mission is actively running"""
        return self.phase in [
            MissionPhase.SEARCHING,
            MissionPhase.TARGET_FOUND,
            MissionPhase.DELIVERING
        ]