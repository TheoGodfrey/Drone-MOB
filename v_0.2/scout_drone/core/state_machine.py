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
# ... (existing code) ...
            # --- Scout/Utility (MOB Search) Mission ---
            ['start_mission', MissionPhase.IDLE, MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            ['preflight_success', MissionPhase.PREFLIGHT, MissionPhase.TAKEOFF, 'after', '_run_takeoff'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.SEARCHING, 'after', '_run_search_step', 'if', '_is_mob_search'],
# ... (existing code) ...
            ['start_patrol_mission', MissionPhase.STANDBY, MissionPhase.PATROLLING, 'after', '_run_patrol'],
            ['patrol_battery_low', MissionPhase.PATROLLING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],
            ['patrol_complete', MissionPhase.PATROLLING, MissionPhase.RETURNING, 'after', '_run_return_to_home'],

            # --- NEW: Overwatch Mission (Scout/Utility Drone) ---
            # FIX: This is now a 2-part command. 
            # 1. GCS sends START_VIDEO_STREAM
            # 2. GCS sends START_OVERWATCH
            ['start_video_stream', [MissionPhase.IDLE, MissionPhase.PATROLLING, MissionPhase.STANDBY], MissionPhase.IDLE, 'after', '_run_start_video_stream'],
            ['start_overwatch_mission', [MissionPhase.IDLE, MissionPhase.STANDBY, MissionPhase.PATROLLING], MissionPhase.PREFLIGHT, 'after', '_run_preflight'],
            ['takeoff_success', MissionPhase.TAKEOFF, MissionPhase.OVERWATCH, 'after', '_run_overwatch', 'if', '_is_overwatch'],
            ['start_overwatch_mission', MissionRequest.PATROLLING, MissionPhase.OVERWATCH, 'after', '_run_overwatch'],
            ['overwatch_complete', MissionPhase.OVERWATCH, MissionPhase.RETURNING, 'after', '_run_return_to_home'],

            # --- Common End-of-Mission Paths ---
# ... (existing code) ...
