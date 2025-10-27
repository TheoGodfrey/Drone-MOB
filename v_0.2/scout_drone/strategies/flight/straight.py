from core.drone import Position

class DirectFlightStrategy:  # No inheritance needed
    """Direct flight algorithm - fly straight to target"""
    def get_next_position(self, drone, target_position):
        """Get the next position to fly to (directly to target)"""
        return target_position