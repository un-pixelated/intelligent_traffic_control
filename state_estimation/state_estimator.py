"""
Complete traffic state estimation system.
Integrates lane tracking, queue estimation, and smoothing.
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

from state_estimation.lane_state_tracker import LaneStateTracker, LaneState
from state_estimation.queue_estimator import QueueEstimator
from state_estimation.smoothing import MultiVariableEMA


@dataclass
class IntersectionState:
    """Complete intersection traffic state"""
    timestamp: float
    lane_states: Dict[str, LaneState]
    approach_metrics: Dict[str, Dict[str, float]]  # approach -> metrics
    total_vehicles: int
    total_stopped: int
    has_emergency: bool
    emergency_approach: Optional[str] = None


class TrafficStateEstimator:
    """
    Complete traffic state estimation system.
    Produces smoothed, reliable state estimates for control algorithms.
    """
    
    def __init__(self, lane_ids: List[str], enable_smoothing: bool = True):
        """
        Initialize state estimator
        
        Args:
            lane_ids: List of all lane IDs
            enable_smoothing: Whether to apply EMA smoothing
        """
        print("Initializing Traffic State Estimator...")
        
        # Core components
        self.lane_tracker = LaneStateTracker(lane_ids, history_length=50)
        self.queue_estimator = QueueEstimator(
            bin_size=5.0,
            max_distance=100.0,
            speed_threshold=0.5
        )
        
        # Smoothing (if enabled)
        self.enable_smoothing = enable_smoothing
        if enable_smoothing:
            # Different smoothing factors for different metrics
            self.smoother = MultiVariableEMA(alphas={
                'queue_length': 0.3,      # Moderate smoothing
                'density': 0.4,           # Less smoothing (changes quickly)
                'avg_waiting_time': 0.2,  # More smoothing (noisy)
                'vehicle_count': 0.5      # Light smoothing (discrete)
            })
        
        self.lane_ids = lane_ids
        
        print(f"✓ State estimator ready ({len(lane_ids)} lanes)")
    
    def update(self, perceived_vehicles: List, current_time: float) -> IntersectionState:
        """
        Update state estimation with new perception data
        
        Args:
            perceived_vehicles: List of PerceivedVehicle objects
            current_time: Current simulation time
            
        Returns:
            Complete intersection state
        """
        # Update lane tracker
        self.lane_tracker.update(perceived_vehicles, current_time)
        
        # Get raw lane states
        raw_states = self.lane_tracker.get_all_states()
        
        # Apply smoothing if enabled
        if self.enable_smoothing:
            smoothed_states = self._smooth_states(raw_states)
        else:
            smoothed_states = raw_states
        
        # Compute approach-level metrics
        approach_metrics = {}
        for approach in ['N', 'S', 'E', 'W']:
            approach_metrics[approach] = self.lane_tracker.get_approach_metrics(approach)
        
        # Aggregate statistics
        total_vehicles = sum(s.vehicle_count for s in smoothed_states.values())
        total_stopped = sum(s.stopped_vehicles for s in smoothed_states.values())
        
        # Emergency vehicle handling
        has_emergency = any(s.has_emergency_vehicle for s in smoothed_states.values())
        emergency_approach = None
        if has_emergency:
            # Find which approach has emergency vehicle
            for approach, metrics in approach_metrics.items():
                if metrics['has_emergency']:
                    emergency_approach = approach
                    break
        
        # Create intersection state
        state = IntersectionState(
            timestamp=current_time,
            lane_states=smoothed_states,
            approach_metrics=approach_metrics,
            total_vehicles=total_vehicles,
            total_stopped=total_stopped,
            has_emergency=has_emergency,
            emergency_approach=emergency_approach
        )
        
        return state
    
    def _smooth_states(self, states: Dict[str, LaneState]) -> Dict[str, LaneState]:
        """Apply EMA smoothing to lane states"""
        smoothed_states = {}
        
        for lane_id, state in states.items():
            # Prepare values for smoothing
            values = {
                'queue_length': state.queue_length,
                'density': state.density,
                'avg_waiting_time': state.avg_waiting_time,
                'vehicle_count': float(state.vehicle_count)
            }
            
            # Apply smoothing
            smoothed_values = self.smoother.update(lane_id, values)
            
            # Create smoothed state (copy original, update smoothed fields)
            smoothed_state = LaneState(
                lane_id=state.lane_id,
                vehicle_count=int(smoothed_values['vehicle_count']),
                queue_length=smoothed_values['queue_length'],
                density=smoothed_values['density'],
                avg_speed=state.avg_speed,  # Don't smooth speed (too responsive)
                avg_waiting_time=smoothed_values['avg_waiting_time'],
                stopped_vehicles=state.stopped_vehicles,
                has_emergency_vehicle=state.has_emergency_vehicle,
                emergency_vehicle_distance=state.emergency_vehicle_distance,
                timestamp=state.timestamp,
                vehicle_distances=state.vehicle_distances,
                vehicle_speeds=state.vehicle_speeds
            )
            
            smoothed_states[lane_id] = smoothed_state
        
        return smoothed_states
    
    def get_state_vector_for_rl(self, state: IntersectionState) -> np.ndarray:
        """
        Convert intersection state to feature vector for RL
        
        Returns:
            Numpy array of shape (n_features,) suitable for RL input
        """
        features = []
        
        # Per-approach features (4 approaches × 4 features = 16)
        for approach in ['N', 'S', 'E', 'W']:
            metrics = state.approach_metrics[approach]
            
            # Normalize features to [0, 1] range
            features.append(min(metrics['total_queue_length'] / 50.0, 1.0))  # Queue
            features.append(min(metrics['avg_density'] * 10, 1.0))  # Density
            features.append(min(metrics['avg_waiting_time'] / 60.0, 1.0))  # Wait time
            features.append(float(metrics['has_emergency']))  # Emergency flag
        
        return np.array(features, dtype=np.float32)
    
    def print_summary(self, state: IntersectionState):
        """Print human-readable state summary"""
        print(f"\n{'='*70}")
        print(f"Traffic State @ t={state.timestamp:.1f}s")
        print(f"{'='*70}")
        
        print(f"Total vehicles: {state.total_vehicles} | Stopped: {state.total_stopped}")
        
        if state.has_emergency:
            print(f"🚨 EMERGENCY VEHICLE in {state.emergency_approach} approach!")
        
        print(f"\nPer-Approach Summary:")
        for approach in ['N', 'S', 'E', 'W']:
            metrics = state.approach_metrics[approach]
            print(f"  {approach}: {metrics['total_vehicles']:2d} veh | "
                  f"Queue: {metrics['total_queue_length']:5.1f}m | "
                  f"Wait: {metrics['avg_waiting_time']:4.1f}s | "
                  f"Stopped: {metrics['stopped_vehicles']:2d}")
        
        print(f"{'='*70}\n")
