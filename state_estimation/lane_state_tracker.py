"""
Tracks traffic state for each lane - DAY 2 PRODUCTION VERSION.

Computes queue length, density, and waiting time from perceived vehicles.
All thresholds and algorithms formally specified in Day 2 architecture doc.

Key Improvements from Day 1:
- Fixed waiting time tracking (from stop_time, not first_seen)
- Added queue_vehicle_count to LaneState
- Made LaneState immutable (frozen=True)
- Increased cleanup timeout (5s → 10s)
- Added validation hooks
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from perception.types import PerceivedVehicle


@dataclass(frozen=True)
class LaneState:
    """
    Traffic state for a single lane - FROZEN INTERFACE.
    
    Immutable to prevent accidental mutation by control algorithms.
    Do NOT add/remove fields without architecture review (Days 2-5).
    
    Physical Interpretation:
        - queue_length: Spatial extent of stopped vehicles (meters)
        - density: Vehicle concentration (vehicles per 100m)
        - avg_waiting_time: Mean delay of currently stopped vehicles
        - avg_speed: Mean velocity of all vehicles
    
    Thresholds (Day 2 Architecture):
        - Queue distance threshold: 30.0 meters
        - Queue speed threshold: 0.5 m/s
        - Density normalization: 100.0 meters
    """
    # Identity
    lane_id: str
    timestamp: float
    
    # Basic Counts
    vehicle_count: int = 0
    stopped_vehicles: int = 0
    
    # Queue Metrics
    queue_length: float = 0.0              # Meters from stop line
    queue_vehicle_count: int = 0           # Number of vehicles in queue
    
    # Flow Metrics
    density: float = 0.0                   # Vehicles per 100m
    avg_speed: float = 0.0                 # m/s
    avg_waiting_time: float = 0.0          # seconds
    
    # Emergency Handling
    has_emergency_vehicle: bool = False
    emergency_vehicle_distance: Optional[float] = None
    
    # Raw Data (tuples for immutability)
    vehicle_distances: Tuple[float, ...] = field(default_factory=tuple)
    vehicle_speeds: Tuple[float, ...] = field(default_factory=tuple)


class LaneStateTracker:
    """
    Tracks traffic state for all lanes at intersection.
    
    Maintains history and computes aggregate statistics using frozen,
    immutable LaneState objects.
    
    Algorithm Specifications (Day 2):
        - Queue definition: distance ≤ 30m AND speed < 0.5 m/s
        - Waiting time: From stop event, NOT from first appearance
        - Density: vehicles / 100m (normalized)
        - Cleanup: Remove vehicles not seen for 10 seconds
    """
    
    # Queue Detection Parameters (Day 2 Architecture - DO NOT MODIFY)
    STOPPED_SPEED_THRESHOLD = 0.5    # m/s - effectively stopped
    QUEUE_DISTANCE_THRESHOLD = 30.0  # meters - queue detection zone
    LANE_LENGTH = 100.0              # meters - normalization constant
    CLEANUP_TIMEOUT = 10.0           # seconds - memory cleanup threshold
    
    def __init__(self, lane_ids: List[str], history_length: int = 50):
        """
        Initialize lane state tracker.
        
        Args:
            lane_ids: List of lane IDs to track
            history_length: Number of timesteps to keep in history
        
        CRITICAL: No LaneState objects are created here.
        All states are created in update() with proper timestamps.
        """
        self.lane_ids = lane_ids
        self.history_length = history_length
        
        # Current state for each lane - EMPTY until first update()
        # Invariant: After first update(), contains exactly one entry per lane_id
        self.current_states: Dict[str, LaneState] = {}
        
        # Historical states (for smoothing and analysis)
        self.state_history: Dict[str, deque] = {
            lid: deque(maxlen=history_length) for lid in lane_ids
        }
        
        # Vehicle tracking
        self.vehicle_first_seen: Dict[int, float] = {}          # track_id -> timestamp
        self.vehicle_stop_time: Dict[int, Optional[float]] = {} # track_id -> stop timestamp
        self.vehicle_last_speed: Dict[int, float] = {}          # track_id -> previous speed
        self.vehicle_last_lane: Dict[int, str] = {}             # track_id -> lane_id
        
        print(f"✓ Initialized tracker for {len(lane_ids)} lanes")
        print(f"  Queue thresholds: {self.QUEUE_DISTANCE_THRESHOLD}m, {self.STOPPED_SPEED_THRESHOLD}m/s")
    
    def update(self, perceived_vehicles: List[PerceivedVehicle], current_time: float):
        """
        Update lane states based on perceived vehicles.
        
        Creates a complete snapshot: one LaneState per lane_id, every timestep.
        Empty lanes produce zero-valued states (not missing entries).
        
        Args:
            perceived_vehicles: List of PerceivedVehicle objects
            current_time: Current simulation time in seconds
        
        Postcondition: len(self.current_states) == len(self.lane_ids)
        """
        # Group vehicles by lane first (for efficiency)
        # CRITICAL: Initialize ALL lanes, even those with no vehicles
        vehicles_by_lane: Dict[str, List[PerceivedVehicle]] = {
            lid: [] for lid in self.lane_ids
        }
        
        for vehicle in perceived_vehicles:
            # Track vehicle first appearance
            if vehicle.track_id not in self.vehicle_first_seen:
                self.vehicle_first_seen[vehicle.track_id] = current_time
                self.vehicle_stop_time[vehicle.track_id] = None
                self.vehicle_last_speed[vehicle.track_id] = 0.0
            
            # Track vehicle lane
            if vehicle.lane_id:
                self.vehicle_last_lane[vehicle.track_id] = vehicle.lane_id
                
                if vehicle.lane_id in vehicles_by_lane:
                    vehicles_by_lane[vehicle.lane_id].append(vehicle)
        
        # Update stop/start times for all vehicles
        self._update_stop_times(perceived_vehicles, current_time)
        
        # Compute state for each lane
        # INVARIANT: Create state for EVERY lane, even if empty
        new_states = {}
        for lane_id in self.lane_ids:
            vehicles = vehicles_by_lane[lane_id]
            new_states[lane_id] = self._compute_lane_state(
                lane_id, vehicles, current_time
            )
        
        # INVARIANT CHECK: Complete snapshot guarantee
        assert len(new_states) == len(self.lane_ids), \
            f"Incomplete snapshot: {len(new_states)} states for {len(self.lane_ids)} lanes"
        
        # Update current states and history
        self.current_states = new_states
        for lane_id, state in new_states.items():
            self.state_history[lane_id].append(state)
        
        # Clean up old vehicle tracking data
        self._cleanup_old_vehicles(perceived_vehicles, current_time)
    
    def _update_stop_times(self, vehicles: List[PerceivedVehicle], current_time: float):
        """
        Update stop/start times for all vehicles.
        
        Fixes Day 1 bug: waiting time now tracks from stop event, not first_seen.
        """
        for v in vehicles:
            # Calculate speed magnitude
            speed = np.sqrt(v.velocity[0]**2 + v.velocity[1]**2)
            
            # Get previous speed
            prev_speed = self.vehicle_last_speed.get(v.track_id, speed)
            
            # Detect stop event
            if speed < self.STOPPED_SPEED_THRESHOLD:
                if v.track_id not in self.vehicle_stop_time or \
                   self.vehicle_stop_time[v.track_id] is None:
                    # Vehicle just stopped
                    self.vehicle_stop_time[v.track_id] = current_time
            else:
                # Vehicle is moving - reset stop time
                self.vehicle_stop_time[v.track_id] = None
            
            # Update last speed
            self.vehicle_last_speed[v.track_id] = speed
    
    def _compute_lane_state(self, 
                           lane_id: str,
                           vehicles: List[PerceivedVehicle],
                           current_time: float) -> LaneState:
        """
        Compute complete state for a single lane.
        
        Returns immutable LaneState object.
        """
        if len(vehicles) == 0:
            return LaneState(lane_id=lane_id, timestamp=current_time)
        
        # Extract vehicle metrics
        distances = []
        speeds = []
        stopped_count = 0
        queued_vehicles = []
        
        for v in vehicles:
            # Distance
            if v.distance_to_stop_line >= 0:
                distances.append(v.distance_to_stop_line)
            
            # Speed
            speed = np.sqrt(v.velocity[0]**2 + v.velocity[1]**2)
            speeds.append(speed)
            
            # Stopped count
            if speed < self.STOPPED_SPEED_THRESHOLD:
                stopped_count += 1
            
            # Queue detection
            if (v.distance_to_stop_line >= 0 and 
                v.distance_to_stop_line <= self.QUEUE_DISTANCE_THRESHOLD and
                speed < self.STOPPED_SPEED_THRESHOLD):
                queued_vehicles.append(v)
        
        # Basic stats
        vehicle_count = len(vehicles)
        avg_speed = np.mean(speeds) if speeds else 0.0
        
        # Queue metrics
        if queued_vehicles:
            queue_length = max(v.distance_to_stop_line for v in queued_vehicles)
            queue_vehicle_count = len(queued_vehicles)
        else:
            queue_length = 0.0
            queue_vehicle_count = 0
        
        # Density (vehicles per 100m)
        density = (vehicle_count / self.LANE_LENGTH) * 100.0
        
        # Waiting time (FIXED: from stop time, not first seen)
        waiting_times = []
        for v in vehicles:
            speed = np.sqrt(v.velocity[0]**2 + v.velocity[1]**2)
            
            # Only count waiting time if vehicle is currently stopped
            if speed < self.STOPPED_SPEED_THRESHOLD:
                stop_time = self.vehicle_stop_time.get(v.track_id)
                if stop_time is not None:
                    waiting_time = current_time - stop_time
                    waiting_times.append(waiting_time)
        
        avg_waiting_time = np.mean(waiting_times) if waiting_times else 0.0
        
        # Emergency vehicle detection
        emergency_vehicles = [v for v in vehicles if v.is_emergency]
        has_emergency = len(emergency_vehicles) > 0
        emergency_distance = None
        
        if emergency_vehicles:
            emergency_distances = [
                v.distance_to_stop_line for v in emergency_vehicles
                if v.distance_to_stop_line >= 0
            ]
            if emergency_distances:
                emergency_distance = min(emergency_distances)
        
        # Create immutable state
        return LaneState(
            lane_id=lane_id,
            timestamp=current_time,
            vehicle_count=vehicle_count,
            stopped_vehicles=stopped_count,
            queue_length=queue_length,
            queue_vehicle_count=queue_vehicle_count,
            density=density,
            avg_speed=avg_speed,
            avg_waiting_time=avg_waiting_time,
            has_emergency_vehicle=has_emergency,
            emergency_vehicle_distance=emergency_distance,
            vehicle_distances=tuple(distances),
            vehicle_speeds=tuple(speeds)
        )
    
    def _cleanup_old_vehicles(self, 
                             current_vehicles: List[PerceivedVehicle],
                             current_time: float):
        """
        Remove tracking data for vehicles that have left.
        
        Increased timeout from 5s to 10s for safety (Day 2 improvement).
        """
        current_track_ids = {v.track_id for v in current_vehicles}
        
        # Find vehicles to remove
        to_remove = []
        for track_id in self.vehicle_first_seen.keys():
            if track_id not in current_track_ids:
                time_since_first_seen = current_time - self.vehicle_first_seen[track_id]
                if time_since_first_seen > self.CLEANUP_TIMEOUT:
                    to_remove.append(track_id)
        
        # Remove old vehicles
        for track_id in to_remove:
            self.vehicle_first_seen.pop(track_id, None)
            self.vehicle_stop_time.pop(track_id, None)
            self.vehicle_last_speed.pop(track_id, None)
            self.vehicle_last_lane.pop(track_id, None)
    
    # ========== Query Methods ==========
    
    def get_lane_state(self, lane_id: str) -> Optional[LaneState]:
        """Get current state for a lane."""
        return self.current_states.get(lane_id)
    
    def get_approach_state(self, approach: str) -> Dict[str, LaneState]:
        """
        Get states for all lanes in an approach.
        
        Args:
            approach: 'N', 'S', 'E', or 'W'
        """
        return {
            lid: state for lid, state in self.current_states.items()
            if lid.startswith(approach + '_')
        }
    
    def get_all_states(self) -> Dict[str, LaneState]:
        """Get current states for all lanes."""
        return self.current_states.copy()
    
    def get_approach_metrics(self, approach: str) -> Dict[str, float]:
        """
        Get aggregate metrics for an approach.
        
        Returns:
            Dictionary with total_vehicles, total_queue_length, etc.
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
        
        # Aggregate metrics
        total_vehicles = sum(s.vehicle_count for s in states.values())
        total_queue_length = sum(s.queue_length for s in states.values())
        avg_density = np.mean([s.density for s in states.values()])
        
        # Waiting time: weighted average by stopped vehicles
        total_waiting = sum(
            s.avg_waiting_time * s.stopped_vehicles 
            for s in states.values()
        )
        total_stopped = sum(s.stopped_vehicles for s in states.values())
        avg_waiting_time = (total_waiting / total_stopped) if total_stopped > 0 else 0.0
        
        has_emergency = any(s.has_emergency_vehicle for s in states.values())
        
        return {
            'total_vehicles': total_vehicles,
            'total_queue_length': total_queue_length,
            'avg_density': avg_density,
            'avg_waiting_time': avg_waiting_time,
            'stopped_vehicles': total_stopped,
            'has_emergency': has_emergency
        }
    
    # ========== Validation Methods ==========
    
    def validate_state(self, state: LaneState) -> List[str]:
        """
        Validate LaneState physical constraints.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Physical bounds
        if state.queue_length < 0:
            errors.append(f"Negative queue length: {state.queue_length}")
        if state.queue_length > self.LANE_LENGTH:
            errors.append(f"Queue exceeds lane: {state.queue_length} > {self.LANE_LENGTH}")
        
        if state.density < 0:
            errors.append(f"Negative density: {state.density}")
        if state.density > 25.0:  # ~25 vehicles/100m = jam density
            errors.append(f"Density exceeds jam: {state.density}")
        
        if state.avg_waiting_time < 0:
            errors.append(f"Negative waiting time: {state.avg_waiting_time}")
        
        # Logical consistency
        if state.queue_vehicle_count > state.vehicle_count:
            errors.append(
                f"More queued than total: {state.queue_vehicle_count} > {state.vehicle_count}"
            )
        
        if state.stopped_vehicles > state.vehicle_count:
            errors.append(
                f"More stopped than total: {state.stopped_vehicles} > {state.vehicle_count}"
            )
        
        return errors
