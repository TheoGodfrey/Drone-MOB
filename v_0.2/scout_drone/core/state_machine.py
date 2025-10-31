"""
Formal mission state machine for a *single drone*.
(Refactored for MQTT publishing)
"""
from enum import Enum
from transitions.extensions.asyncio import AsyncMachine
from .comms import MqttClient

class MissionPhase(Enum):
    """Mission phases (Updated)"""
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    SEARCHING = "SEARCHING"
    TARGET_PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
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
    Manages the mission's formal state transitions and reports
    changes to the Coordinator via MQTT.
    """
    def __init__(self, controller: 'MissionController', mqtt: MqttClient):
        """
        Initializes and attaches the state machine to the controller.
        """
        self.controller = controller
        self.mqtt = mqtt
        states = [e for e in MissionPhase]

        # Define all valid transitions
        transitions = [
            # Mission start (triggered by MQTT)
            ['start_mission', MissionPhase.IDLE, MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            
            ['preflight_success', MissionPhase.PREFLIGHT, MissionPhase.TAKEOFF, 'after', '_run_takeoff'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.SEARCHING, 'after', '_run_search_step'],
            
            # Search path
            ['target_sighted', MissionPhase.SEARCHING, MissionPhase.TARGET_PENDING_CONFIRMATION, 'after', '_run_pending_confirmation'],
            ['search_complete_negative', MissionPhase.SEARCHING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            
            # GCS/Coordinator Confirmation Path
            ['gcs_confirm_target', MissionPhase.TARGET_PENDING_CONFIRMATION, MissionPhase.DELIVERING, 'after', '_run_delivery'],
            ['gcs_reject_target', MissionPhase.TARGET_PENDING_CONFIRMATION, MissionPhase.SEARCHING, 'after', '_run_search_step'],
            
            ['delivery_complete', MissionPhase.DELIVERING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            ['arrived_home', MissionPhase.RETURNING, MissionPhase.LANDING, 'after', '_run_land'],
            ['land_complete', MissionPhase.LANDING, MissionPhase.COMPLETED, 'after', '_log_mission_summary'],
            ['trigger_emergency', '*', MissionPhase.EMERGENCY, 'after', '_run_emergency_land']
        ]

        self.machine = AsyncMachine(
            model=controller,
            states=states,
            transitions=transitions,
            initial=MissionPhase.IDLE,
            send_event=True,
            # NEW: Automatically publish every state change to MQTT
            after_state_change=self._publish_state_change
        )

    async def _publish_state_change(self, event):
        """Callback to publish the new state to the Coordinator."""
        new_state = event.state.value
        drone_id = self.controller.drone.id
        await self.mqtt.publish(f"fleet/state/{drone_id}", {
            "state": new_state,
            "timestamp": asyncio.get_event_loop().time()
        })

