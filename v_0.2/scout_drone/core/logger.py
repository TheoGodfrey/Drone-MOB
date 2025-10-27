"""
Minimal logger for single-drone system
"""

import time

class MissionLogger:
    """Simplified mission logger with minimal overhead"""
    def __init__(self):
        self.log_file = "mission.log"
    
    def log(self, message: str, level: str = "info"):
        """Log a message with the specified level"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level.upper()}] {message}\n"
        with open(self.log_file, "a") as f:
            f.write(log_line)