"""
Day 2 State Estimation Validation Script.

Tests and validates the production state estimation implementation.
Runs unit tests and system-level validation checks.
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from perception.types import PerceivedVehicle
from state_estimation.lane_state_tracker import LaneStateTracker, LaneState
from state_estimation.state_estimator import TrafficStateEstimator


# ========== Unit Tests ==========

def test_queue_length_correctness():
    """Test 1: Queue length computation."""
    print("\n" + "="*70)
    print("TEST 1: Queue Length Correctness")
    print("="*70)
    
    # Setup
    lane_ids = ["N_in_0"]
    tracker = LaneStateTracker(lane_ids)
    
    # Test case: 3 stopped vehicles at different distances
    vehicles = [
        PerceivedVehicle(
            track_id=1, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 225.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=5.0
        ),
        PerceivedVehicle(
            track_id=2, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 235.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=15.0
        ),
        PerceivedVehicle(
            track_id=3, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 245.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=25.0
        ),
    ]
    
    # Update
    tracker.update(vehicles, current_time=10.0)
    state = tracker.get_lane_state("N_in_0")
    
    # Validate
    expected_queue_length = 25.0
    expected_queue_count = 3
    
    assert state.queue_length == expected_queue_length, \
        f"Queue length: expected {expected_queue_length}, got {state.queue_length}"
    assert state.queue_vehicle_count == expected_queue_count, \
        f"Queue count: expected {expected_queue_count}, got {state.queue_vehicle_count}"
    
    print(f"✓ Queue length: {state.queue_length}m (expected {expected_queue_length}m)")
    print(f"✓ Queue vehicles: {state.queue_vehicle_count} (expected {expected_queue_count})")


def test_waiting_time_accumulation():
    """Test 2: Waiting time tracks from stop event."""
    print("\n" + "="*70)
    print("TEST 2: Waiting Time Accumulation")
    print("="*70)
    
    # Setup
    lane_ids = ["N_in_0"]
    tracker = LaneStateTracker(lane_ids)
    
    # t=0: Vehicle appears, moving
    vehicle_moving = PerceivedVehicle(
        track_id=1, class_name="car", is_emergency=False, confidence=1.0,
        position=(200.0, 220.0), velocity=(0, 5.0),  # Moving at 5 m/s
        lane_id="N_in_0", distance_to_stop_line=10.0
    )
    tracker.update([vehicle_moving], current_time=0.0)
    
    # t=5: Vehicle stops
    vehicle_stopped = PerceivedVehicle(
        track_id=1, class_name="car", is_emergency=False, confidence=1.0,
        position=(200.0, 210.0), velocity=(0, 0),  # Now stopped
        lane_id="N_in_0", distance_to_stop_line=5.0
    )
    tracker.update([vehicle_stopped], current_time=5.0)
    
    # t=10: Check waiting time
    tracker.update([vehicle_stopped], current_time=10.0)
    state = tracker.get_lane_state("N_in_0")
    
    # Validate: Should be 5 seconds (from stop time), NOT 10 seconds (from first seen)
    expected_waiting = 5.0
    tolerance = 0.1
    
    assert abs(state.avg_waiting_time - expected_waiting) < tolerance, \
        f"Waiting time: expected {expected_waiting}s, got {state.avg_waiting_time}s"
    
    print(f"✓ Waiting time: {state.avg_waiting_time:.1f}s (expected {expected_waiting}s)")
    print(f"  Vehicle first seen at t=0.0s")
    print(f"  Vehicle stopped at t=5.0s")
    print(f"  Current time t=10.0s")
    print(f"  Correct waiting time = 10.0 - 5.0 = 5.0s ✓")


def test_memory_cleanup():
    """Test 3: Memory cleanup removes old vehicles."""
    print("\n" + "="*70)
    print("TEST 3: Memory Cleanup")
    print("="*70)
    
    # Setup
    lane_ids = ["N_in_0"]
    tracker = LaneStateTracker(lane_ids)
    
    # Add 10 vehicles
    vehicles = [
        PerceivedVehicle(
            track_id=i, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 210.0 + i*7), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=5.0 + i*7
        )
        for i in range(10)
    ]
    tracker.update(vehicles, current_time=0.0)
    
    initial_count = len(tracker.vehicle_first_seen)
    print(f"  Initial tracked vehicles: {initial_count}")
    
    # Remove all vehicles
    tracker.update([], current_time=1.0)
    
    # Wait for cleanup (timeout is 10 seconds)
    tracker.update([], current_time=12.0)
    
    final_count = len(tracker.vehicle_first_seen)
    print(f"  After cleanup: {final_count}")
    
    assert final_count == 0, f"Memory not cleaned: {final_count} vehicles still tracked"
    print(f"✓ Memory cleaned: 0 vehicles tracked (expected 0)")


# ========== System-Level Validation ==========

def test_temporal_stability(duration: int = 50):
    """Test 4: Temporal stability of smoothing."""
    print("\n" + "="*70)
    print("TEST 4: Temporal Stability")
    print("="*70)
    
    from simulation.sumo_interface import SUMOInterface
    from perception.sumo_adapter import SumoPerceptionAdapter
    from perception.lane_mapper import LaneMapper
    
    # Setup
    config_file = str(project_root / "sumo_networks" / "simple_4way" / "sumo.cfg")
    intersection_config = str(project_root / "config" / "intersection_config.yaml")
    
    sumo = SUMOInterface(config_file, use_gui=False)
    sumo.start()
    
    lane_mapper = LaneMapper(intersection_config)
    perception = SumoPerceptionAdapter(sumo, lane_mapper)
    
    lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    
    # Test with and without smoothing
    estimator_raw = TrafficStateEstimator(lane_ids, enable_smoothing=False)
    estimator_smooth = TrafficStateEstimator(lane_ids, enable_smoothing=True)
    
    # Collect data
    time_series = []
    raw_queues = []
    smooth_queues = []
    
    try:
        for step in range(duration * 10):  # 0.1s per step
            sumo.step()
            current_time = sumo.get_current_time()
            
            # Perceive
            vehicles = perception.perceive(current_time)
            
            # Estimate (both raw and smoothed)
            state_raw = estimator_raw.update(vehicles, current_time)
            state_smooth = estimator_smooth.update(vehicles, current_time)
            
            # Track North approach queue
            time_series.append(current_time)
            raw_queues.append(state_raw.approach_metrics['N']['total_queue_length'])
            smooth_queues.append(state_smooth.approach_metrics['N']['total_queue_length'])
    
    finally:
        sumo.close()
    
    # Analyze stability
    raw_variance = np.var(raw_queues)
    smooth_variance = np.var(smooth_queues)
    variance_reduction = (1 - smooth_variance / raw_variance) * 100
    
    print(f"  Raw variance: {raw_variance:.2f}")
    print(f"  Smoothed variance: {smooth_variance:.2f}")
    print(f"  Variance reduction: {variance_reduction:.1f}%")
    
    assert variance_reduction > 10, "Smoothing should reduce variance by >10%"
    print(f"✓ Smoothing reduces variance by {variance_reduction:.1f}%")
    
    # Plot
    plt.figure(figsize=(12, 4))
    plt.plot(time_series, raw_queues, 'r-', alpha=0.5, label='Raw', linewidth=1)
    plt.plot(time_series, smooth_queues, 'b-', label='Smoothed', linewidth=2)
    plt.xlabel('Time (s)')
    plt.ylabel('Queue Length (m)')
    plt.title('Temporal Stability: Raw vs Smoothed Queue Length')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_path = project_root / "results" / "day2_validation" / "temporal_stability.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    print(f"✓ Plot saved: {output_path}")


def test_physical_plausibility():
    """Test 5: Physical constraint validation."""
    print("\n" + "="*70)
    print("TEST 5: Physical Plausibility")
    print("="*70)
    
    from simulation.sumo_interface import SUMOInterface
    from perception.sumo_adapter import SumoPerceptionAdapter
    from perception.lane_mapper import LaneMapper
    
    # Setup
    config_file = str(project_root / "sumo_networks" / "simple_4way" / "sumo.cfg")
    intersection_config = str(project_root / "config" / "intersection_config.yaml")
    
    sumo = SUMOInterface(config_file, use_gui=False)
    sumo.start()
    
    lane_mapper = LaneMapper(intersection_config)
    perception = SumoPerceptionAdapter(sumo, lane_mapper)
    
    lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    estimator = TrafficStateEstimator(lane_ids, enable_smoothing=True)
    
    violations = []
    
    try:
        for step in range(300):  # 30 seconds
            sumo.step()
            current_time = sumo.get_current_time()
            
            vehicles = perception.perceive(current_time)
            state = estimator.update(vehicles, current_time)
            
            # Validate
            errors = estimator.validate_state(state)
            if errors:
                violations.extend(errors)
    
    finally:
        sumo.close()
    
    if violations:
        print("✗ Physical constraints violated:")
        for v in violations[:10]:  # Show first 10
            print(f"    {v}")
    else:
        print("✓ All physical constraints satisfied")
    
    assert len(violations) == 0, f"Found {len(violations)} constraint violations"


# ========== Main ==========

def main():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("DAY 2 STATE ESTIMATION VALIDATION")
    print("="*70)
    
    try:
        # Unit tests
        test_queue_length_correctness()
        test_waiting_time_accumulation()
        test_memory_cleanup()
        
        # System tests (require SUMO)
        print("\n" + "="*70)
        print("SYSTEM-LEVEL TESTS (requires SUMO)")
        print("="*70)
        
        test_temporal_stability()
        test_physical_plausibility()
        
        # Summary
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        print("\nDay 2 state estimation is production-ready.")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
