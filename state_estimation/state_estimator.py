"""
Complete traffic state estimation system - DAY 2 PRODUCTION VERSION.

Integrates lane tracking, smoothing, and intersection-level aggregation.
All algorithms and parameters formally specified in Day 2 architecture doc.

Key Improvements from Day 1:
- Made IntersectionState immutable (frozen=True)
- Added total_waiting_time aggregation
- Added max_queue_length tracking
- Added emergency_distance to IntersectionState
- Removed RL feature vector method (out of scope)
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

from perception.types import PerceivedVehicle
from state_estimation.lane_state_tracker import LaneStateTracker, LaneState
from state_estimation.smoothing import MultiVariableEMA


@dataclass(frozen=True)
class IntersectionState:
    """
    Complete intersection traffic state - FROZEN INTERFACE.
    
    Output of state estimation, input to control.
    Immutable to prevent accidental mutation.
    
    Usage by Control:
        - Adaptive control: Uses approach_metrics for phase selection
        - Emergency control: Uses has_emergency + emergency_approach + emergency_distance
        - Queue management: Uses max_queue_length for spillback prevention
    
    Do NOT add/remove fields without architecture review (Days 2-5).
    """
    # Temporal
    timestamp: float
    
    # Per-Lane State
    lane_states: Dict[str, LaneState]
    
    # Per-Approach Aggregates
    approach_metrics: Dict[str, Dict[str, float]]
    
    # Intersection-Level Aggregates
    total_vehicles: int
    total_stopped: int
    total_waiting_time: float          # Sum of all vehicle waiting times
    max_queue_length: float            # Longest queue in intersection
    
    # Emergency Status
    has_emergency: bool
    emergency_approach: Optional[str] = None
    emergency_distance: Optional[float] = None  # Distance to stop line


class TrafficStateEstimator:
    """
    Complete traffic state estimation system.
    
    Produces smoothed, temporally stable state estimates for control algorithms.
    
    Pipeline:
        PerceivedVehicles → LaneStateTracker → Raw States → Smoothing → IntersectionState
    
    Smoothing Factors (Day 2 Architecture):
        - queue_length: α=0.3 (moderate smoothing)
        - density: α=0.4 (less smoothing, faster response)
        - avg_waiting_time: α=0.2 (heavy smoothing, very noisy signal)
        - vehicle_count: α=0.5 (light smoothing, discrete jumps)
    """
    
    def __init__(self, lane_ids: List[str], enable_smoothing: bool = True):
        """
        Initialize state estimator.
        
        Args:
            lane_ids: List of all lane IDs to track
            enable_smoothing: Whether to apply EMA smoothing
        """
        print("Initializing Traffic State Estimator...")
        
        # Core component
        self.lane_tracker = LaneStateTracker(lane_ids, history_length=50)
        
        # Smoothing (Day 2 Architecture - DO NOT MODIFY)
        self.enable_smoothing = enable_smoothing
        if enable_smoothing:
            self.smoother = MultiVariableEMA(alphas={
                'queue_length': 0.3,      # Moderate: balance stability & response
                'density': 0.4,           # Less: density changes quickly
                'avg_waiting_time': 0.2,  # Heavy: very noisy, saw-tooth from departures
                'vehicle_count': 0.5      # Light: discrete jumps, need responsiveness
            })
        
        self.lane_ids = lane_ids
        
        print(f"✓ State estimator ready ({len(lane_ids)} lanes)")
        print(f"  Smoothing: {'enabled' if enable_smoothing else 'disabled'}")
    
    def update(self, 
               perceived_vehicles: List[PerceivedVehicle], 
               current_time: float) -> IntersectionState:
        """
        Update state estimation with new perception data.
        
        Args:
            perceived_vehicles: List of PerceivedVehicle objects from perception
            current_time: Current simulation time (seconds)
        
        Returns:
            Immutable IntersectionState object
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
        
        # Aggregate intersection-level statistics
        total_vehicles = sum(s.vehicle_count for s in smoothed_states.values())
        total_stopped = sum(s.stopped_vehicles for s in smoothed_states.values())
        
        # Total waiting time (NEW - Day 2)
        total_waiting_time = sum(
            s.avg_waiting_time * s.stopped_vehicles
            for s in smoothed_states.values()
        )
        
        # Max queue length (NEW - Day 2)
        queue_lengths = [s.queue_length for s in smoothed_states.values()]
        max_queue_length = max(queue_lengths) if queue_lengths else 0.0
        
        # Emergency vehicle handling
        has_emergency = any(s.has_emergency_vehicle for s in smoothed_states.values())
        emergency_approach = None
        emergency_distance = None
        
        if has_emergency:
            # Find approach with emergency vehicle
            for approach, metrics in approach_metrics.items():
                if metrics['has_emergency']:
                    emergency_approach = approach
                    break
            
            # Find closest emergency vehicle distance (NEW - Day 2)
            emergency_states = [
                s for s in smoothed_states.values()
                if s.has_emergency_vehicle and s.emergency_vehicle_distance is not None
            ]
            if emergency_states:
                emergency_distance = min(
                    s.emergency_vehicle_distance for s in emergency_states
                )
        
        # Create immutable intersection state
        state = IntersectionState(
            timestamp=current_time,
            lane_states=smoothed_states,
            approach_metrics=approach_metrics,
            total_vehicles=total_vehicles,
            total_stopped=total_stopped,
            total_waiting_time=total_waiting_time,
            max_queue_length=max_queue_length,
            has_emergency=has_emergency,
            emergency_approach=emergency_approach,
            emergency_distance=emergency_distance
        )
        
        return state
    
    def _smooth_states(self, states: Dict[str, LaneState]) -> Dict[str, LaneState]:
        """
        Apply EMA smoothing to lane states.
        
        Creates new immutable LaneState objects with smoothed values.
        Does NOT smooth: has_emergency, stopped_vehicles, avg_speed, raw data.
        """
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
            
            # Create new immutable state with smoothed values
            smoothed_state = LaneState(
                lane_id=state.lane_id,
                timestamp=state.timestamp,
                vehicle_count=int(smoothed_values['vehicle_count']),
                stopped_vehicles=state.stopped_vehicles,  # Do NOT smooth
                queue_length=smoothed_values['queue_length'],
                queue_vehicle_count=state.queue_vehicle_count,  # Do NOT smooth
                density=smoothed_values['density'],
                avg_speed=state.avg_speed,  # Do NOT smooth (already averaged)
                avg_waiting_time=smoothed_values['avg_waiting_time'],
                has_emergency_vehicle=state.has_emergency_vehicle,  # Do NOT smooth
                emergency_vehicle_distance=state.emergency_vehicle_distance,
                vehicle_distances=state.vehicle_distances,  # Raw data unchanged
                vehicle_speeds=state.vehicle_speeds
            )
            
            smoothed_states[lane_id] = smoothed_state
        
        return smoothed_states
    
    # ========== Utility Methods ==========
    
    def print_summary(self, state: IntersectionState):
        """Print human-readable state summary for debugging."""
        print(f"\n{'='*70}")
        print(f"Traffic State @ t={state.timestamp:.1f}s")
        print(f"{'='*70}")
        
        print(f"Total vehicles: {state.total_vehicles} | Stopped: {state.total_stopped}")
        print(f"Total waiting time: {state.total_waiting_time:.1f}s | Max queue: {state.max_queue_length:.1f}m")
        
        if state.has_emergency:
            emergency_str = f"🚨 EMERGENCY VEHICLE in {state.emergency_approach} approach"
            if state.emergency_distance is not None:
                emergency_str += f" ({state.emergency_distance:.1f}m from stop line)"
            print(emergency_str)
        
        print(f"\nPer-Approach Summary:")
        for approach in ['N', 'S', 'E', 'W']:
            metrics = state.approach_metrics[approach]
            print(f"  {approach}: {metrics['total_vehicles']:2d} veh | "
                  f"Queue: {metrics['total_queue_length']:5.1f}m | "
                  f"Wait: {metrics['avg_waiting_time']:4.1f}s | "
                  f"Stopped: {metrics['stopped_vehicles']:2d}")
        
        print(f"{'='*70}\n")
    
    def validate_state(self, state: IntersectionState) -> List[str]:
        """
        Validate IntersectionState consistency.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Validate each lane
        for lane_id, lane_state in state.lane_states.items():
            lane_errors = self.lane_tracker.validate_state(lane_state)
            errors.extend([f"Lane {lane_id}: {e}" for e in lane_errors])
        
        # Cross-lane consistency
        sum_vehicles = sum(s.vehicle_count for s in state.lane_states.values())
        if sum_vehicles != state.total_vehicles:
            errors.append(
                f"Vehicle count mismatch: sum={sum_vehicles}, total={state.total_vehicles}"
            )
        
        sum_stopped = sum(s.stopped_vehicles for s in state.lane_states.values())
        if sum_stopped != state.total_stopped:
            errors.append(
                f"Stopped count mismatch: sum={sum_stopped}, total={state.total_stopped}"
            )
        
        # Physical bounds
        if state.max_queue_length < 0:
            errors.append(f"Negative max queue: {state.max_queue_length}")
        
        if state.total_waiting_time < 0:
            errors.append(f"Negative total waiting: {state.total_waiting_time}")
        
        return errors
    
    def reset(self):
        """
        Reset state estimator for new simulation episode.
        
        Clears all history and tracking data.
        Returns to initialization state (no LaneState objects exist).
        """
        # Reset lane tracker to empty state (like __init__)
        self.lane_tracker.current_states.clear()
        
        # Clear history for all lanes
        for lane_id in self.lane_ids:
            self.lane_tracker.state_history[lane_id].clear()
        
        # Clear vehicle tracking
        self.lane_tracker.vehicle_first_seen.clear()
        self.lane_tracker.vehicle_stop_time.clear()
        self.lane_tracker.vehicle_last_speed.clear()
        self.lane_tracker.vehicle_last_lane.clear()
        
        # Reset smoother if enabled
        if self.enable_smoothing:
            for var_filter in self.smoother.filters.values():
                var_filter.reset()
