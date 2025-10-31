"""
Formal mission state machine using the 'transitions' library.
"""
from enum import Enum
from transitions.extensions.asyncio import AsyncMachine

class MissionPhase(Enum):
    """Mission phases (Updated)"""
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    SEARCHING = "SEARCHING"
    TARGET_PENDING_CONFIRMATION = "PENDING_CONFIRMATION" # NEW
    DELIVERING = "DELIVERING"
    RETURNING = "RETURNING"
    LANDING = "LANDING"
    COMPLETED = "COMPLETED"
    EMERGENCY = "EMERGENCY"
    
    def is_active(self) -> bool:
        """Check if mission is actively running"""
        return self in [
            MissionPhase.SEARCHING,
            MissionPhase.TARGET_PENDING_CONFIRMATION,
            MissionPhase.DELIVERING
        ]

class MissionStateMachine:
    """
    Manages the mission's formal state transitions by attaching an
    AsyncMachine to the MissionController instance.
    """
    def __init__(self, controller):
        """
        Initializes and attaches the state machine to the controller.
        """
        states = [e for e in MissionPhase]

        # Define all valid transitions
        transitions = [
            ['start_mission', MissionPhase.IDLE, MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            
            # Preflight path
            ['preflight_success', MissionPhase.PREFLIGHT, MissionPhase.TAKEOFF, 'after', '_run_takeoff'],
            
            # Takeoff path
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.SEARCHING, 'after', '_run_search_step'],
            
            # --- UPDATED Search/Confirm/Deliver Path ---
            # Search finds a target, moves to PENDING
            ['target_sighted', MissionPhase.SEARCHING, MissionPhase.TARGET_PENDING_CONFIRMATION, 'after', '_run_pending_confirmation'],
            
            # Search finishes with no target
            ['search_complete_negative', MissionPhase.SEARCHING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            
            # Operator confirms the target
            ['operator_confirm_target', MissionPhase.TARGET_PENDING_CONFIRMATION, MissionPhase.DELIVERING, 'after', '_run_delivery'],
            
            # Operator rejects the target
            ['operator_reject_target', MissionPhase.TARGET_PENDING_CONFIRMATION, MissionPhase.SEARCHING, 'after', '_run_search_step'],
            
            # Delivery path
            ['delivery_complete', MissionPhase.DELIVERING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            # --- End of Updated Path ---
            
            # Return path
            ['arrived_home', MissionPhase.RETURNING, MissionPhase.LANDING, 'after', '_run_land'],
            
            # Land path
            ['land_complete', MissionPhase.LANDING, MissionPhase.COMPLETED, 'after', '_log_mission_summary'],

            # Emergency path (can be triggered from any state)
            ['trigger_emergency', '*', MissionPhase.EMERGENCY, 'after', '_run_emergency_land']
        ]

        self.machine = AsyncMachine(
            model=controller,
            states=states,
            transitions=transitions,
            initial=MissionPhase.IDLE,
            send_event=True
        )
