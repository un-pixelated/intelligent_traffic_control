"""
Ground truth perception using SUMO's internal data.
Bypasses computer vision - for control algorithm development.
"""

from typing import List, Tuple
from dataclasses import dataclass
import numpy as np


@dataclass
class PerceivedVehicle:
    """Vehicle from ground truth"""
    track_id: int
    bbox: Tuple[float, float, float, float]  # Dummy
    class_name: str
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    lane_id: str
    distance_to_stop_line: float
    is_emergency: bool
    confidence: float = 1.0


class GroundTruthPerception:
    """
    Uses SUMO's ground truth data instead of computer vision.
    Perfect for testing control algorithms without perception noise.
    """
    
    def __init__(self, lane_mapper):
        self.lane_mapper = lane_mapper
        self.emergency_types = {'ambulance', 'fire_truck'}
    
    def process_sumo_vehicles(self, sumo_vehicles: List) -> List[PerceivedVehicle]:
        """Convert SUMO vehicles to PerceivedVehicle format"""
        perceived = []
        
        for v in sumo_vehicles:
            # Assign lane
            lane_id = self.lane_mapper.assign_lane(v.position)
            
            # Distance to stop line
            if lane_id:
                dist = self.lane_mapper.get_distance_to_stop_line(v.position, lane_id)
            else:
                dist = -1.0
            
            # Velocity from SUMO (convert angle to vx, vy)
            angle_rad = np.radians(v.angle)
            vx = v.speed * np.sin(angle_rad)
            vy = v.speed * np.cos(angle_rad)
            
            perceived.append(PerceivedVehicle(
                track_id=hash(v.id) % 100000,  # Stable ID from vehicle ID
                bbox=(0, 0, 0, 0),  # Not used
                class_name=v.type,
                position=v.position,
                velocity=(vx, vy),
                lane_id=lane_id,
                distance_to_stop_line=dist,
                is_emergency=(v.type in self.emergency_types),
                confidence=1.0
            ))
        
        return perceived
