"""
Maps detected vehicles to specific lanes.
Determines which lane each vehicle occupies based on position.
"""

import numpy as np
import yaml
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LaneInfo:
    """Lane geometry and properties"""
    lane_id: str
    direction: str  # 'north', 'south', 'east', 'west'
    approach: str   # 'N', 'S', 'E', 'W'
    lane_index: int
    type: str      # 'through', 'left_turn'
    entry_line: Tuple[float, float]
    stop_line: Tuple[float, float]


class LaneMapper:
    """
    Maps vehicle positions to lanes.
    Uses geometric rules to assign vehicles to specific lanes.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize lane mapper
        
        Args:
            config_path: Path to intersection_config.yaml
        """
        # Load configuration
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.intersection_center = (
            config['intersection']['center']['x'],
            config['intersection']['center']['y']
        )
        self.lane_width = config['intersection']['lane_width']
        
        # Parse lane definitions
        self.lanes: Dict[str, LaneInfo] = {}
        for lane_id, lane_data in config['intersection']['lanes'].items():
            self.lanes[lane_id] = LaneInfo(
                lane_id=lane_id,
                direction=lane_data['direction'],
                approach=lane_data['approach'],
                lane_index=lane_data['lane_index'],
                type=lane_data['type'],
                entry_line=(lane_data['entry_line']['x'], lane_data['entry_line']['y']),
                stop_line=(lane_data['stop_line']['x'], lane_data['stop_line']['y'])
            )
        
        print(f"✓ Loaded {len(self.lanes)} lane definitions")
    
    def assign_lane(self, position: Tuple[float, float], 
                   heading: Optional[float] = None) -> Optional[str]:
        """
        Assign vehicle to lane based on position
        
        Args:
            position: (x, y) in SUMO world coordinates
            heading: Vehicle heading in degrees (0=North, 90=East)
            
        Returns:
            Lane ID or None if not in any lane
        """
        x, y = position
        cx, cy = self.intersection_center
        
        # Determine which approach based on position relative to center
        # North: y > cy, South: y < cy, East: x > cx, West: x < cx
        
        # Calculate offset from center
        dx = x - cx
        dy = y - cy
        
        # Determine primary direction
        if abs(dx) > abs(dy):
            # East-West approach
            if dx > 0:
                approach = 'E'
                # Calculate lane index based on y position
                lane_offset = cy - y  # Distance from center line
            else:
                approach = 'W'
                lane_offset = y - cy
        else:
            # North-South approach
            if dy > 0:
                approach = 'N'
                lane_offset = x - cx
            else:
                approach = 'S'
                lane_offset = cx - x
        
        # Convert offset to lane index (0, 1, 2)
        # Lane 0: rightmost, Lane 2: leftmost (left turn)
        lane_index = int(lane_offset / self.lane_width + 1.5)  # Center on lane 1
        lane_index = max(0, min(2, lane_index))  # Clamp to [0, 2]
        
        # Construct lane ID
        lane_id = f"{approach}_in_{lane_index}"
        
        # Verify lane exists
        if lane_id in self.lanes:
            return lane_id
        
        return None
    
    def get_distance_to_stop_line(self, position: Tuple[float, float], 
                                  lane_id: str) -> float:
        """
        Calculate distance from vehicle to stop line
        
        Args:
            position: Vehicle position (x, y)
            lane_id: Assigned lane ID
            
        Returns:
            Distance in meters (positive = before stop line)
        """
        if lane_id not in self.lanes:
            return -1.0
        
        lane = self.lanes[lane_id]
        x, y = position
        stop_x, stop_y = lane.stop_line
        
        # Distance depends on approach direction
        if lane.direction == 'north':
            # Approaching from north (y decreasing)
            distance = y - stop_y
        elif lane.direction == 'south':
            # Approaching from south (y increasing)
            distance = stop_y - y
        elif lane.direction == 'east':
            # Approaching from east (x decreasing)
            distance = x - stop_x
        else:  # west
            # Approaching from west (x increasing)
            distance = stop_x - x
        
        return distance
    
    def get_lane_info(self, lane_id: str) -> Optional[LaneInfo]:
        """Get lane information by ID"""
        return self.lanes.get(lane_id)
    
    def get_lanes_by_approach(self, approach: str) -> List[str]:
        """Get all lane IDs for an approach (N, S, E, W)"""
        return [lid for lid, lane in self.lanes.items() 
                if lane.approach == approach]
    
    def is_vehicle_in_intersection(self, position: Tuple[float, float], 
                                   threshold: float = 10.0) -> bool:
        """Check if vehicle is inside intersection"""
        x, y = position
        cx, cy = self.intersection_center
        
        dist = np.sqrt((x - cx)**2 + (y - cy)**2)
        return dist < threshold
