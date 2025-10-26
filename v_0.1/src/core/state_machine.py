"""
Mission state machine for scout drone
"""

from enum import Enum


class DroneState(Enum):
    """Mission states"""
    IDLE = "idle"
    PREFLIGHT = "preflight"
    CLIMBING = "climbing"
    SCANNING = "scanning"
    TARGET_ACQUIRED = "target_acquired"
    APPROACHING = "approaching"
    ON_TARGET = "on_target"
    RETURNING = "returning"
    LANDING = "landing"
    MISSION_COMPLETE = "mission_complete"
    EMERGENCY = "emergency"


class TargetType(Enum):
    """Classification types"""
    UNKNOWN = "unknown"
    PERSON = "person"
    BOAT = "boat"
    DEBRIS = "debris"
    FALSE_POSITIVE = "false_positive"
