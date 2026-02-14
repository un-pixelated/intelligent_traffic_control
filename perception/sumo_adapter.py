"""
SUMO-based ground truth perception adapter.

Uses TraCI to get perfect vehicle information from SUMO simulation.
Replaces the old ground_truth_perception.py module.

Author: Architecture Review Day 1
Date: 2026-02-14
"""
import numpy as np
from typing import List, Dict
from perception.base import PerceptionAdapter
from perception.types import PerceivedVehicle
from perception.emergency_detection import EmergencyVehicleDetector
from perception.lane_mapper import LaneMapper
from simulation.sumo_interface import SUMOInterface


class SumoPerceptionAdapter(PerceptionAdapter):
    """
    Ground truth perception using SUMO TraCI.
    
    This adapter converts SUMO's internal vehicle state into
    the standardized PerceivedVehicle format. It provides
    perfect information with no noise or detection failures.
    
    Usage:
        sumo = SUMOInterface(config_file)
        sumo.start()
        
        perception = SumoPerceptionAdapter(sumo, lane_mapper)
        vehicles = perception.perceive(sumo.get_current_time())
    """
    
    def __init__(self, 
                 sumo_interface: SUMOInterface,
                 lane_mapper: LaneMapper):
        """
        Initialize SUMO perception adapter.
        
        Args:
            sumo_interface: Active SUMO connection
            lane_mapper: Lane geometry and assignment logic
        """
        if not sumo_interface.connected:
            raise ValueError("SUMO interface must be connected before creating adapter")
        
        self.sumo = sumo_interface
        self.lane_mapper = lane_mapper
        
        # Track ID management
        self._track_id_map: Dict[str, int] = {}
        self._next_track_id = 1
        
        # Statistics
        self._perceive_call_count = 0
    
    def perceive(self, timestamp: float) -> List[PerceivedVehicle]:
        """
        Get ground truth vehicle perceptions from SUMO.
        
        Returns perfect information about all vehicles:
        - Exact positions and velocities
        - Correct lane assignments
        - Accurate stop-line distances
        - confidence=1.0 for all detections
        
        Args:
            timestamp: Current simulation time (seconds)
        
        Returns:
            List of PerceivedVehicle objects
        """
        self._perceive_call_count += 1
        
        # Get all vehicles from SUMO via TraCI
        sumo_vehicles = self.sumo.get_all_vehicles()
        
        perceived = []
        for v in sumo_vehicles:
            # Convert SUMO vehicle ID to stable integer track ID
            track_id = self._get_track_id(v.id)
            
            # Assign vehicle to intersection lane
            lane_id = self.lane_mapper.assign_lane(v.position)
            
            # Calculate distance to stop line
            if lane_id is not None:
                distance = self.lane_mapper.get_distance_to_stop_line(
                    v.position, lane_id
                )
            else:
                distance = -1.0
            
            # Convert velocity from speed+angle to Cartesian (vx, vy)
            angle_rad = np.radians(v.angle)
            vx = v.speed * np.sin(angle_rad)
            vy = v.speed * np.cos(angle_rad)
            
            # Detect emergency vehicles
            is_emergency = EmergencyVehicleDetector.is_emergency_gt(v.type)
            
            # Create perceived vehicle
            perceived_vehicle = PerceivedVehicle(
                track_id=track_id,
                class_name=v.type,
                is_emergency=is_emergency,
                confidence=1.0,
                position=v.position,
                velocity=(vx, vy),
                lane_id=lane_id,
                distance_to_stop_line=distance,
                bbox=(0, 0, 0, 0)
            )
            
            perceived.append(perceived_vehicle)
        
        return perceived
    
    def reset(self):
        """Reset track ID mapping for new simulation episode."""
        self._track_id_map.clear()
        self._next_track_id = 1
    
    @property
    def name(self) -> str:
        """Return human-readable adapter name."""
        return "SUMO Ground Truth"
    
    def get_statistics(self) -> dict:
        """Get runtime statistics for monitoring."""
        return {
            'total_vehicles_tracked': len(self._track_id_map),
            'active_tracks': len(self._track_id_map),
            'perceive_calls': self._perceive_call_count,
            'next_track_id': self._next_track_id
        }
    
    def _get_track_id(self, sumo_vehicle_id: str) -> int:
        """
        Convert SUMO vehicle ID to stable integer track ID.
        
        Maintains consistent mapping across frames.
        """
        if sumo_vehicle_id not in self._track_id_map:
            self._track_id_map[sumo_vehicle_id] = self._next_track_id
            self._next_track_id += 1
        
        return self._track_id_map[sumo_vehicle_id]
