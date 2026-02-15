"""
Unit test for Day 2 stabilization fixes.
Tests that LaneStateTracker behaves correctly with frozen LaneState.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from state_estimation.lane_state_tracker import LaneStateTracker, LaneState
from state_estimation.state_estimator import TrafficStateEstimator
from perception.types import PerceivedVehicle


def test_initialization():
    """Test that tracker initializes with empty current_states."""
    print("\n" + "="*70)
    print("TEST: Initialization (No Placeholder States)")
    print("="*70)
    
    lane_ids = ['N_in_0', 'S_in_0', 'E_in_0', 'W_in_0']
    tracker = LaneStateTracker(lane_ids)
    
    # CRITICAL: current_states must be empty before first update()
    assert len(tracker.current_states) == 0, \
        f"FAIL: current_states should be empty, got {len(tracker.current_states)} entries"
    
    print("✓ current_states is empty at initialization")
    print("✓ No TypeError from missing timestamp")


def test_first_update_empty():
    """Test first update with no vehicles creates complete snapshot."""
    print("\n" + "="*70)
    print("TEST: First Update (Empty - Zero Vehicles)")
    print("="*70)
    
    lane_ids = ['N_in_0', 'S_in_0', 'E_in_0', 'W_in_0']
    tracker = LaneStateTracker(lane_ids)
    
    # First update with no vehicles
    tracker.update([], current_time=0.0)
    
    # CRITICAL: All lanes must exist in snapshot
    assert len(tracker.current_states) == len(lane_ids), \
        f"FAIL: Expected {len(lane_ids)} lanes, got {len(tracker.current_states)}"
    
    # CRITICAL: All lanes must have timestamp
    for lane_id in lane_ids:
        state = tracker.get_lane_state(lane_id)
        assert state is not None, f"FAIL: Lane {lane_id} missing from snapshot"
        assert state.timestamp == 0.0, f"FAIL: Lane {lane_id} wrong timestamp"
        assert state.vehicle_count == 0, f"FAIL: Lane {lane_id} should have 0 vehicles"
        assert state.queue_length == 0.0, f"FAIL: Lane {lane_id} should have 0 queue"
    
    print(f"✓ All {len(lane_ids)} lanes present in snapshot")
    print("✓ All lanes have correct timestamp")
    print("✓ Empty lanes have zero metrics")


def test_first_update_with_vehicles():
    """Test first update with vehicles creates complete snapshot."""
    print("\n" + "="*70)
    print("TEST: First Update (With Vehicles)")
    print("="*70)
    
    lane_ids = ['N_in_0', 'S_in_0']
    tracker = LaneStateTracker(lane_ids)
    
    # Vehicle in N_in_0 only
    vehicles = [
        PerceivedVehicle(
            track_id=1, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 220.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=10.0
        )
    ]
    
    tracker.update(vehicles, current_time=5.0)
    
    # Both lanes must exist
    assert len(tracker.current_states) == 2, \
        f"FAIL: Expected 2 lanes, got {len(tracker.current_states)}"
    
    # N_in_0 should have vehicle
    n_state = tracker.get_lane_state("N_in_0")
    assert n_state is not None, "FAIL: N_in_0 missing"
    assert n_state.vehicle_count == 1, f"FAIL: N_in_0 should have 1 vehicle, got {n_state.vehicle_count}"
    assert n_state.timestamp == 5.0, f"FAIL: N_in_0 wrong timestamp"
    
    # S_in_0 should be empty but exist
    s_state = tracker.get_lane_state("S_in_0")
    assert s_state is not None, "FAIL: S_in_0 missing"
    assert s_state.vehicle_count == 0, f"FAIL: S_in_0 should have 0 vehicles, got {s_state.vehicle_count}"
    assert s_state.timestamp == 5.0, f"FAIL: S_in_0 wrong timestamp"
    
    print("✓ Lane with vehicle has correct count")
    print("✓ Empty lane exists with zero metrics")
    print("✓ Both lanes have same timestamp")


def test_subsequent_updates():
    """Test that subsequent updates replace entire snapshot."""
    print("\n" + "="*70)
    print("TEST: Subsequent Updates")
    print("="*70)
    
    lane_ids = ['N_in_0']
    tracker = LaneStateTracker(lane_ids)
    
    # Update 1: One vehicle
    vehicles_1 = [
        PerceivedVehicle(
            track_id=1, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 220.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=10.0
        )
    ]
    tracker.update(vehicles_1, current_time=1.0)
    state_1 = tracker.get_lane_state("N_in_0")
    assert state_1.vehicle_count == 1, "Update 1 failed"
    assert state_1.timestamp == 1.0, "Update 1 timestamp wrong"
    
    # Update 2: Two vehicles
    vehicles_2 = [
        PerceivedVehicle(
            track_id=1, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 220.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=10.0
        ),
        PerceivedVehicle(
            track_id=2, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 230.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=20.0
        )
    ]
    tracker.update(vehicles_2, current_time=2.0)
    state_2 = tracker.get_lane_state("N_in_0")
    assert state_2.vehicle_count == 2, "Update 2 failed"
    assert state_2.timestamp == 2.0, "Update 2 timestamp wrong"
    
    # Update 3: Back to empty
    tracker.update([], current_time=3.0)
    state_3 = tracker.get_lane_state("N_in_0")
    assert state_3.vehicle_count == 0, "Update 3 failed"
    assert state_3.timestamp == 3.0, "Update 3 timestamp wrong"
    
    print("✓ Snapshots correctly replaced each update")
    print("✓ Timestamps updated correctly")
    print("✓ Empty update resets to zero")


def test_state_estimator_integration():
    """Test that TrafficStateEstimator works with fixed tracker."""
    print("\n" + "="*70)
    print("TEST: TrafficStateEstimator Integration")
    print("="*70)
    
    lane_ids = ['N_in_0', 'S_in_0', 'E_in_0', 'W_in_0']
    estimator = TrafficStateEstimator(lane_ids, enable_smoothing=False)
    
    # First update with no vehicles
    intersection_state = estimator.update([], current_time=0.0)
    
    # Check intersection state
    assert intersection_state.timestamp == 0.0, "Wrong timestamp"
    assert len(intersection_state.lane_states) == len(lane_ids), \
        f"Expected {len(lane_ids)} lanes, got {len(intersection_state.lane_states)}"
    assert intersection_state.total_vehicles == 0, "Should have 0 vehicles"
    assert intersection_state.max_queue_length == 0.0, "Should have 0 max queue"
    
    print(f"✓ IntersectionState has all {len(lane_ids)} lanes")
    print("✓ Aggregation works with zero vehicles")
    print("✓ No errors on first timestep")


def test_reset():
    """Test that reset() clears state correctly."""
    print("\n" + "="*70)
    print("TEST: Reset Functionality")
    print("="*70)
    
    lane_ids = ['N_in_0']
    estimator = TrafficStateEstimator(lane_ids, enable_smoothing=False)
    
    # Do an update
    vehicles = [
        PerceivedVehicle(
            track_id=1, class_name="car", is_emergency=False, confidence=1.0,
            position=(200.0, 220.0), velocity=(0, 0),
            lane_id="N_in_0", distance_to_stop_line=10.0
        )
    ]
    estimator.update(vehicles, current_time=1.0)
    
    # Verify state exists
    assert len(estimator.lane_tracker.current_states) == 1, "Update failed"
    
    # Reset
    estimator.reset()
    
    # CRITICAL: After reset, current_states should be empty (like __init__)
    assert len(estimator.lane_tracker.current_states) == 0, \
        "FAIL: current_states should be empty after reset"
    
    # Vehicle tracking should be cleared
    assert len(estimator.lane_tracker.vehicle_first_seen) == 0, \
        "FAIL: vehicle_first_seen not cleared"
    
    print("✓ Reset clears current_states to empty")
    print("✓ Reset clears vehicle tracking")
    print("✓ No TypeError from reset()")


def main():
    """Run all unit tests."""
    print("\n" + "="*70)
    print("DAY 2 STABILIZATION: UNIT TESTS")
    print("="*70)
    
    try:
        test_initialization()
        test_first_update_empty()
        test_first_update_with_vehicles()
        test_subsequent_updates()
        test_state_estimator_integration()
        test_reset()
        
        print("\n" + "="*70)
        print("✓ ALL UNIT TESTS PASSED")
        print("="*70)
        print("\nDay 2 stabilization fixes are correct.")
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
