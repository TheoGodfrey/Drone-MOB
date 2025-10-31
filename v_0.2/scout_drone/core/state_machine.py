"""
Formal mission state machine using the 'transitions' library.
(Refactored for 3-Drone Fleet and MQTT reporting)
"""
from enum import Enum
from transitions.extensions.asyncio import AsyncMachine
from .comms import MqttClient

class MissionPhase(Enum):
    """Mission phases"""
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    SEARCHING = "SEARCHING"
    TARGET_PENDING_CONFIRMATION = "TARGET_PENDING_CONFIRMATION"
    TARGET_CONFIRMED = "TARGET_CONFIRMED"
    DELIVERING = "DELIVERING"
    STANDBY = "STANDBY"
    RETURNING = "RETURNING"
    LANDING = "LANDING"
    COMPLETED = "COMPLETED"
    EMERGENCY = "EMERGENCY"
    
    # NEW: Operational Modes
    PATROLLING = "PATROLLING"
    OVERWATCH = "OVERWATCH"
    LOCAL_OPERATOR_CONTROL = "LOCAL_OPERATOR_CONTROL"


class MissionStateMachine:
    """
    Manages the mission's formal state transitions by attaching an
    AsyncMachine to the MissionController instance.
    
    Also publishes all state changes to MQTT.
    """
    def __init__(self, controller, mqtt: MqttClient):
        self.controller = controller
        self.mqtt = mqtt
        self.drone_id = controller.drone.id
        
        states = [e for e in MissionPhase]

        transitions = [
            # --- Scout/Utility (MOB Search) Mission ---
            ['start_mission', MissionPhase.IDLE, MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            ['preflight_success', MissionPhase.PREFLIGHT, MissionPhase.TAKEOFF, 'after', '_run_takeoff'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.SEARCHING, 'after', '_run_search_step', 'if', '_is_mob_search'],
            ['target_sighted', MissionPhase.SEARCHING, MissionPhase.TARGET_PENDING_CONFIRMATION, 'after', '_request_operator_confirmation'],
            ['search_complete_negative', MissionPhase.SEARCHING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            
            # Operator Confirmation Path
            ['confirm_target', MissionPhase.TARGET_PENDING_CONFIRMATION, MissionPhase.TARGET_CONFIRMED, 'after', '_request_delivery'],
            ['reject_target', MissionPhase.TARGET_PENDING_CONFIRMATION, MissionPhase.SEARCHING, 'after', '_handle_rejection'],
            
            # --- Payload Drone (Standby) Mission ---
            ['start_standby_mission', MissionPhase.IDLE, MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.STANDBY, 'after', '_run_standby', 'if', '_is_standby'],

            # --- Payload Drone (Delivery) Mission ---
            ['start_delivery_mission', MissionPhase.IDLE, MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.DELIVERING, 'after', '_run_payload_delivery', 'if', '_is_delivery'],
            ['start_delivery_mission', MissionPhase.STANDBY, MissionPhase.DELIVERING, 'after', '_run_payload_delivery'],

            # --- NEW: Patrol Mission (Utility Drone) ---
            ['start_patrol_mission', MissionPhase.IDLE, MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.PATROLLING, 'after', '_run_patrol', 'if', '_is_patrol'],
            # Can also start patrol from standby (e.g., after an event)
            ['start_patrol_mission', MissionPhase.STANDBY, MissionPhase.PATROLLING, 'after', '_run_patrol'],
            ['patrol_battery_low', MissionPhase.PATROLLING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            ['patrol_complete', MissionPhase.PATROLLING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],

            # --- NEW: Overwatch Mission (Scout/Utility Drone) ---
            # Can be triggered from IDLE, or interrupt PATROLLING
            ['start_overwatch_mission', [MissionPhase.IDLE, MissionPhase.STANDBY, MissionPhase.PATROLLING], MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.OVERWATCH, 'after', '_run_overwatch', 'if', '_is_overwatch'],
            # If already flying (e.g. PATROLLING), just transition to OVERWATCH state
            ['start_overwatch_mission', MissionPhase.PATROLLING, MissionPhase.OVERWATCH, 'after', '_run_overwatch'],
            ['overwatch_complete', MissionPhase.OVERWATCH, MissionPhase.RETURNING, 'after', '_run_return_to_home'],

            # --- Common End-of-Mission Paths ---
            ['delivery_request_sent', MissionPhase.TARGET_CONFIRMED, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            ['delivery_complete', MissionPhase.DELIVERING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            ['arrived_home', MissionPhase.RETURNING, MissionPhase.LANDING, 'after', '_run_land'],
            ['land_complete', MissionPhase.LANDING, MissionPhase.COMPLETED, 'after', '_log_mission_summary'],

            # --- NEW: Local Operator Takeover (High Priority) ---
            # Can be triggered from *any* state except EMERGENCY
            ['local_operator_takeover', '*', MissionPhase.LOCAL_OPERATOR_CONTROL, 'after', '_run_local_operator_takeover', 'unless', 'is_EMERGENCY'],
            # When released, go to a safe state (RTL)
            ['local_operator_release', MissionPhase.LOCAL_OPERATOR_CONTROL, MissionPhase.RETURNING, 'after', '_run_return_to_home'],

            # --- Emergency Path ---
            ['trigger_emergency', '*', MissionPhase.EMERGENCY, 'after', '_run_emergency_land']
        ]

        self.machine = AsyncMachine(
            model=controller,
            states=states,
            transitions=transitions,
            initial=MissionPhase.IDLE,
            send_event=True,
            after_state_change='_publish_state_change' 
        )

    async def _publish_state_change(self, event):
        """Callback to publish the new state to MQTT."""
        new_state = event.state.value
        self.controller.logger.log(f"State changed to: {new_state}", "debug")
        await self.mqtt.publish(
            f"fleet/state/{self.drone_id}",
            {"state": new_state}
        )

    # --- Condition Check Methods (for state machine) ---
    
    async def _is_mob_search(self, event):
        return self.controller.current_mission_type == "MOB_SEARCH"
        
    async def _is_standby(self, event):
        return self.controller.current_mission_type == "STANDBY"
        
    async def _is_delivery(self, event):
        return self.controller.current_mission_type == "PAYLOAD_DELIVERY"
        
    async def _is_patrol(self, event):
        return self.controller.current_mission_type == "PATROL"
        
    async def _is_overwatch(self, event):
        return self.controller.current_mission_type == "OVERWATCH"

