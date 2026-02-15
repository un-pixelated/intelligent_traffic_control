# DAY 2 STABILIZATION: BROKEN ASSUMPTIONS

**Date:** 2026-02-15  
**Engineer:** Senior Software Engineer  
**Status:** Analysis Complete

---

## BROKEN ASSUMPTION #1: LaneState Creation in __init__

**Location:** `state_estimation/lane_state_tracker.py:100-102`

**Current Code:**
```python
self.current_states: Dict[str, LaneState] = {
    lid: LaneState(lane_id=lid) for lid in lane_ids
}
```

**Problem:**
1. `LaneState` dataclass requires both `lane_id` AND `timestamp` as mandatory fields (lines 43-44)
2. This code tries to create `LaneState(lane_id=lid)` without `timestamp`
3. Causes `TypeError: LaneState.__init__() missing 1 required positional argument: 'timestamp'`

**Why This Is Wrong:**
- Violates Day 2 rule: "No LaneState objects are created in __init__"
- Creates placeholder states at initialization
- No valid timestamp exists until first update() call
- Even if we added a dummy timestamp (e.g., 0.0), it would violate the "create only in update()" rule

**Correct Behavior:**
- `__init__` should initialize `self.current_states = {}` (empty dict)
- First `update()` call creates all LaneState objects with proper timestamps
- Every subsequent `update()` call creates fresh LaneState snapshots

---

## BROKEN ASSUMPTION #2: Missing Lane Handling in Query Methods

**Location:** `state_estimation/lane_state_tracker.py:315, 329-331`

**Current Code:**
```python
def get_lane_state(self, lane_id: str) -> Optional[LaneState]:
    """Get current state for a lane."""
    return self.current_states.get(lane_id)

def get_all_states(self) -> Dict[str, LaneState]:
    """Get current states for all lanes."""
    return self.current_states.copy()
```

**Problem:**
1. If `update()` has never been called, `current_states` is empty
2. `get_all_states()` returns `{}` instead of containing all lanes
3. Callers expect all lanes to be present (for aggregation, iteration)
4. `get_lane_state()` returns `None` for lanes that haven't been updated

**Why This Is Wrong:**
- Day 2 rule: "update() always returns a complete snapshot: One LaneState per lane_id, every timestep"
- Empty lanes should produce zero-valued states, not missing entries
- Breaks iteration: `for lane_id, state in get_all_states().items()` won't include all lanes

**Correct Behavior:**
- After first `update()`, `get_all_states()` must return exactly `len(self.lane_ids)` entries
- Empty lanes get `LaneState(lane_id=X, timestamp=T)` with all metrics zero
- Every lane must be present in every snapshot

---

## BROKEN ASSUMPTION #3: State History Initialization

**Location:** `state_estimation/lane_state_tracker.py:104-107`

**Current Code:**
```python
# Historical states (for smoothing and analysis)
self.state_history: Dict[str, deque] = {
    lid: deque(maxlen=history_length) for lid in lane_ids
}
```

**Problem:**
- This is actually CORRECT - creates empty deques
- But relies on BROKEN ASSUMPTION #1 being fixed
- If states aren't created in update(), history won't be populated correctly

**Why This Matters:**
- Smoothing relies on history
- Empty history at initialization is fine
- But update() must append to history consistently

**Correct Behavior:**
- Keep initialization as-is (empty deques)
- Ensure update() appends to history for ALL lanes

---

## BROKEN ASSUMPTION #4: Approach Metrics with Missing Lanes

**Location:** `state_estimation/lane_state_tracker.py:333-374`

**Current Code:**
```python
def get_approach_metrics(self, approach: str) -> Dict[str, float]:
    states = self.get_approach_state(approach)
    
    if not states:  # Returns early if no states
        return {
            'total_vehicles': 0,
            'total_queue_length': 0.0,
            ...
        }
```

**Problem:**
- If `current_states` is empty or incomplete, returns zero metrics
- Masks the real issue: lanes should always exist
- Defensive code that hides broken assumptions

**Why This Is Questionable:**
- Good: Defensive against empty dict
- Bad: Allows incomplete snapshots to pass silently
- Should only trigger if approach has no lanes (config error)

**Correct Behavior:**
- After update(), approach should always have states for its lanes
- Empty return is only valid if approach has 0 configured lanes
- Not a fix target, but validates ASSUMPTION #2 is fixed

---

## BROKEN ASSUMPTION #5: TrafficStateEstimator Smoothing

**Location:** `state_estimation/state_estimator.py:188-219`

**Current Code:**
```python
def _smooth_states(self, states: Dict[str, LaneState]) -> Dict[str, LaneState]:
    smoothed_states = {}
    
    for lane_id, state in states.items():
        # ... smoothing logic ...
        smoothed_states[lane_id] = smoothed_state
    
    return smoothed_states
```

**Problem:**
- If `states` is empty (from ASSUMPTION #1), returns empty dict
- Smoothing iterates only over lanes in `states.items()`
- Missing lanes won't be smoothed (and won't exist in output)

**Why This Is Wrong:**
- Should smooth ALL configured lanes
- Empty input dict breaks the complete snapshot invariant

**Correct Behavior:**
- Fix ASSUMPTION #1 so `states` always contains all lanes
- Smoothing preserves complete snapshot

---

## BROKEN ASSUMPTION #6: IntersectionState Aggregation

**Location:** `state_estimation/state_estimator.py:135-146`

**Current Code:**
```python
total_vehicles = sum(s.vehicle_count for s in smoothed_states.values())
total_stopped = sum(s.stopped_vehicles for s in smoothed_states.values())
...
queue_lengths = [s.queue_length for s in smoothed_states.values()]
max_queue_length = max(queue_lengths) if queue_lengths else 0.0
```

**Problem:**
- If `smoothed_states` is empty, these work but give wrong semantics:
  - `sum([])` = 0 ✓ (correct for zero vehicles)
  - `max([])` requires guard (line 146 has it) ✓
- But issue is: empty dict means "no lanes" not "zero vehicles"

**Why This Is Subtle:**
- Code is technically correct (handles empty)
- But empty dict is semantically wrong (should have all lanes)
- Defensive code that masks ASSUMPTION #1

**Correct Behavior:**
- Fix ASSUMPTION #1 so dict is never empty after update()
- These aggregations then work naturally

---

## ROOT CAUSE ANALYSIS

**Primary Root Cause:** BROKEN ASSUMPTION #1

All other issues cascade from trying to create LaneState objects in __init__ without timestamps.

**Fix Priority:**
1. **CRITICAL:** Fix __init__ to not create states
2. **CRITICAL:** Fix update() to always create complete snapshots
3. **VALIDATION:** Ensure query methods work with empty initial state
4. **VALIDATION:** Test with zero vehicles, first timestep

---

## INVARIANTS TO ENFORCE

After fixes, these must hold:

**Invariant 1:** `len(tracker.current_states) == 0` before first update()
**Invariant 2:** `len(tracker.current_states) == len(tracker.lane_ids)` after any update()
**Invariant 3:** `set(tracker.current_states.keys()) == set(tracker.lane_ids)` always after update()
**Invariant 4:** All LaneState objects have `state.timestamp == current_time` from that update()
**Invariant 5:** Empty lanes have all metrics at zero, but state object exists

---

## TEST SCENARIOS TO VALIDATE

1. **Initialization:** Create tracker, call no methods → current_states should be empty
2. **First Update (Empty):** Call update with no vehicles → all lanes exist with zero values
3. **First Update (With Vehicles):** Call update with vehicles → all lanes exist, some non-zero
4. **Subsequent Update:** Call again → all lanes replaced with new states
5. **Lane Query:** get_lane_state() after update → returns state, never None for configured lane
6. **Approach Query:** get_approach_state() after update → returns all approach lanes
7. **Smoothing:** Works with complete snapshots

---

**END OF ANALYSIS**
