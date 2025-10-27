"""
Random search algorithm - simple random pattern
"""

from .__init__ import SearchStrategy
from core.drone import Position
import random

class RandomSearchStrategy(SearchStrategy):
    """Random search algorithm - random pattern for search"""
    def get_next_position(self, drone, search_area, search_size):
        """Get the next position to search (random pattern)"""
        x = random.uniform(
            search_area.x - search_size/2, 
            search_area.x + search_size/2
        )
        y = random.uniform(
            search_area.y - search_size/2, 
            search_area.y + search_size/2
        )
        return Position(x, y, 0)