"""
Tracks traffic state for each lane.
Computes queue length, density, and waiting time from perceived vehicles.
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
import time

from perception.types import PerceivedVehicle


@dataclass
class LaneState:
    """Traffic state for a single lane"""
    lane_id: str
    vehicle_count: int = 0
    queue_length: float = 0.0  # meters
    density: float = 0.0  # vehicles/meter
    avg_speed: float = 0.0  # m/s
    avg_waiting_time: float = 0.0  # seconds
    stopped_vehicles: int = 0
    has_emergency_vehicle: bool = False
    emergency_vehicle_distance: Optional[float] = None
    timestamp: float = 0.0
    
    # Raw vehicle data
    vehicle_distances: List[float] = field(default_factory=list)
    vehicle_speeds: List[float] = field(default_factory=list)


class LaneStateTracker:
    """
    Tracks traffic state for all lanes at intersection.
    Maintains history and computes aggregate statistics.
    """
    
    def __init__(self, lane_ids: List[str], history_length: int = 50):
        """
        Initialize lane state tracker
        
        Args:
            lane_ids: List of lane IDs to track
            history_length: Number of timesteps to keep in history
        """
        self.lane_ids = lane_ids
        self.history_length = history_length
        
        # Current state for each lane
        self.current_states: Dict[str, LaneState] = {
            lid: LaneState(lane_id=lid) for lid in lane_ids
        }
        
        # Historical states (for smoothing and analysis)
        self.state_history: Dict[str, deque] = {
            lid: deque(maxlen=history_length) for lid in lane_ids
        }
        
        # Vehicle tracking (track_id -> first_seen_time)
        self.vehicle_first_seen: Dict[int, float] = {}
        self.vehicle_last_lane: Dict[int, str] = {}
        
        # Constants
        self.STOPPED_SPEED_THRESHOLD = 0.5  # m/s
        self.QUEUE_DISTANCE_THRESHOLD = 30.0  # meters from stop line
        self.LANE_LENGTH = 100.0  # meters (for density calculation)
        
        print(f"✓ Initialized tracker for {len(lane_ids)} lanes")
    
    def update(self, perceived_vehicles: List[PerceivedVehicle], current_time: float):
        """
        Update lane states based on perceived vehicles
        
        Args:
            perceived_vehicles: List of PerceivedVehicle objects
            current_time: Current simulation time in seconds
        """
        # Reset all lane states
        for lane_id in self.lane_ids:
            self.current_states[lane_id] = LaneState(
                lane_id=lane_id,
                timestamp=current_time
            )
        
        # Group vehicles by lane
        vehicles_by_lane: Dict[str, List] = {lid: [] for lid in self.lane_ids}
        
        for vehicle in perceived_vehicles:
            # Track vehicle first appearance
            if vehicle.track_id not in self.vehicle_first_seen:
                self.vehicle_first_seen[vehicle.track_id] = current_time
            
            # Track vehicle lane changes
            if vehicle.lane_id:
                self.vehicle_last_lane[vehicle.track_id] = vehicle.lane_id
                
                if vehicle.lane_id in vehicles_by_lane:
                    vehicles_by_lane[vehicle.lane_id].append(vehicle)
        
        # Compute state for each lane
        for lane_id, vehicles in vehicles_by_lane.items():
            if len(vehicles) == 0:
                continue
            
            state = self.current_states[lane_id]
            
            # Basic counts
            state.vehicle_count = len(vehicles)
            
            # Extract distances and speeds
            distances = []
            speeds = []
            stopped_count = 0
            
            for v in vehicles:
                if v.distance_to_stop_line >= 0:  # Valid distance
                    distances.append(v.distance_to_stop_line)
                    state.vehicle_distances.append(v.distance_to_stop_line)
                
                # Speed magnitude
                speed = np.sqrt(v.velocity[0]**2 + v.velocity[1]**2)
                speeds.append(speed)
                state.vehicle_speeds.append(speed)
                
                if speed < self.STOPPED_SPEED_THRESHOLD:
                    stopped_count += 1
            
            state.stopped_vehicles = stopped_count
            
            # Average speed
            if speeds:
                state.avg_speed = np.mean(speeds)
            
            # Queue length estimation
            # Queue = vehicles within threshold distance that are stopped/slow
            queue_vehicles = [
                d for d, s in zip(distances, speeds)
                if d <= self.QUEUE_DISTANCE_THRESHOLD and s < self.STOPPED_SPEED_THRESHOLD
            ]
            
            if queue_vehicles:
                # Queue length = distance from stop line to furthest queued vehicle
                state.queue_length = max(queue_vehicles)
            else:
                state.queue_length = 0.0
            
            # Density (vehicles per meter)
            if self.LANE_LENGTH > 0:
                state.density = state.vehicle_count / self.LANE_LENGTH
            
            # Waiting time estimation
            waiting_times = []
            for v in vehicles:
                if v.track_id in self.vehicle_first_seen:
                    waiting_time = current_time - self.vehicle_first_seen[v.track_id]
                    
                    # Only count as waiting if vehicle is stopped/slow
                    speed = np.sqrt(v.velocity[0]**2 + v.velocity[1]**2)
                    if speed < self.STOPPED_SPEED_THRESHOLD:
                        waiting_times.append(waiting_time)
            
            if waiting_times:
                state.avg_waiting_time = np.mean(waiting_times)
            
            # Emergency vehicle detection
            emergency_vehicles = [v for v in vehicles if v.is_emergency]
            if emergency_vehicles:
                state.has_emergency_vehicle = True
                # Get closest emergency vehicle distance
                emergency_distances = [
                    v.distance_to_stop_line for v in emergency_vehicles
                    if v.distance_to_stop_line >= 0
                ]
                if emergency_distances:
                    state.emergency_vehicle_distance = min(emergency_distances)
            
            # Store in history
            self.state_history[lane_id].append(state)
        
        # Clean up old vehicle tracking data
        self._cleanup_old_vehicles(perceived_vehicles, current_time)
    
    def _cleanup_old_vehicles(self, current_vehicles: List, current_time: float):
        """Remove tracking data for vehicles that have left"""
        current_track_ids = {v.track_id for v in current_vehicles}
        
        # Remove vehicles not seen for 5 seconds
        to_remove = []
        for track_id, first_seen in self.vehicle_first_seen.items():
            if track_id not in current_track_ids:
                if current_time - first_seen > 5.0:
                    to_remove.append(track_id)
        
        for track_id in to_remove:
            self.vehicle_first_seen.pop(track_id, None)
            self.vehicle_last_lane.pop(track_id, None)
    
    def get_lane_state(self, lane_id: str) -> Optional[LaneState]:
        """Get current state for a lane"""
        return self.current_states.get(lane_id)
    
    def get_approach_state(self, approach: str) -> Dict[str, LaneState]:
        """
        Get states for all lanes in an approach
        
        Args:
            approach: 'N', 'S', 'E', or 'W'
            
        Returns:
            Dictionary of lane_id -> LaneState for that approach
        """
        approach_states = {}
        for lane_id, state in self.current_states.items():
            if lane_id.startswith(approach + '_'):
                approach_states[lane_id] = state
        return approach_states
    
    def get_all_states(self) -> Dict[str, LaneState]:
        """Get current states for all lanes"""
        return self.current_states.copy()
    
    def get_approach_metrics(self, approach: str) -> Dict[str, float]:
        """
        Get aggregate metrics for an approach
        
        Returns:
            Dictionary with total_vehicles, total_queue, avg_waiting_time, etc.
        """
        states = self.get_approach_state(approach)
        
        if not states:
            return {
                'total_vehicles': 0,
                'total_queue_length': 0.0,
                'avg_density': 0.0,
                'avg_waiting_time': 0.0,
                'stopped_vehicles': 0,
                'has_emergency': False
            }
        
        metrics = {
            'total_vehicles': sum(s.vehicle_count for s in states.values()),
            'total_queue_length': sum(s.queue_length for s in states.values()),
            'avg_density': np.mean([s.density for s in states.values()]),
            'avg_waiting_time': np.mean([s.avg_waiting_time for s in states.values() if s.avg_waiting_time > 0] or [0.0]),
            'stopped_vehicles': sum(s.stopped_vehicles for s in states.values()),
            'has_emergency': any(s.has_emergency_vehicle for s in states.values())
        }
        
        return metrics
