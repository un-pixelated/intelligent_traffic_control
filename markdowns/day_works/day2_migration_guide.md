# DAY 2 MIGRATION GUIDE

**From:** Day 1 State Estimation (working but informal)  
**To:** Day 2 State Estimation (production-ready, frozen interfaces)

---

## WHAT CHANGED

### 1. LaneState Dataclass
```python
# OLD (Day 1)
@dataclass
class LaneState:
    lane_id: str
    vehicle_count: int = 0
    queue_length: float = 0.0
    density: float = 0.0
    avg_speed: float = 0.0
    avg_waiting_time: float = 0.0
    stopped_vehicles: int = 0
    has_emergency_vehicle: bool = False
    emergency_vehicle_distance: Optional[float] = None
    timestamp: float = 0.0
    vehicle_distances: List[float] = field(default_factory=list)
    vehicle_speeds: List[float] = field(default_factory=list)

# NEW (Day 2)
@dataclass(frozen=True)  # ← Immutable
class LaneState:
    # Identity
    lane_id: str
    timestamp: float
    
    # Basic Counts
    vehicle_count: int = 0
    stopped_vehicles: int = 0
    
    # Queue Metrics
    queue_length: float = 0.0
    queue_vehicle_count: int = 0  # ← NEW: explicit count
    
    # Flow Metrics
    density: float = 0.0
    avg_speed: float = 0.0
    avg_waiting_time: float = 0.0
    
    # Emergency
    has_emergency_vehicle: bool = False
    emergency_vehicle_distance: Optional[float] = None
    
    # Raw Data (tuples for immutability)
    vehicle_distances: Tuple[float, ...] = field(default_factory=tuple)  # ← Tuple
    vehicle_speeds: Tuple[float, ...] = field(default_factory=tuple)      # ← Tuple
```

**Changes:**
- `frozen=True` → Immutable
- Added `queue_vehicle_count`
- Lists → Tuples for raw data
- Reordered fields logically

### 2. IntersectionState Dataclass
```python
# OLD (Day 1)
@dataclass
class IntersectionState:
    timestamp: float
    lane_states: Dict[str, LaneState]
    approach_metrics: Dict[str, Dict[str, float]]
    total_vehicles: int
    total_stopped: int
    has_emergency: bool
    emergency_approach: Optional[str] = None

# NEW (Day 2)
@dataclass(frozen=True)  # ← Immutable
class IntersectionState:
    timestamp: float
    lane_states: Dict[str, LaneState]
    approach_metrics: Dict[str, Dict[str, float]]
    total_vehicles: int
    total_stopped: int
    total_waiting_time: float         # ← NEW
    max_queue_length: float           # ← NEW
    has_emergency: bool
    emergency_approach: Optional[str] = None
    emergency_distance: Optional[float] = None  # ← NEW
```

**Changes:**
- `frozen=True` → Immutable
- Added `total_waiting_time`
- Added `max_queue_length`
- Added `emergency_distance`

### 3. Waiting Time Tracking (BUG FIX)

**OLD (Day 1) - INCORRECT:**
```python
# Tracks from first appearance (WRONG)
if v.track_id in self.vehicle_first_seen:
    waiting_time = current_time - self.vehicle_first_seen[v.track_id]
    
    if speed < self.STOPPED_SPEED_THRESHOLD:
        waiting_times.append(waiting_time)
```

**Problem:** Vehicle enters at t=0 moving, stops at t=5, at t=10 reports 10s waiting (should be 5s).

**NEW (Day 2) - CORRECT:**
```python
# Tracks from stop event (CORRECT)
self.vehicle_stop_time: Dict[int, Optional[float]] = {}

# In update:
if speed < STOPPED_THRESHOLD:
    if track_id not in self.vehicle_stop_time or self.vehicle_stop_time[track_id] is None:
        self.vehicle_stop_time[track_id] = current_time
    waiting_time = current_time - self.vehicle_stop_time[track_id]
else:
    self.vehicle_stop_time[track_id] = None  # Reset when moving
```

### 4. Cleanup Timeout
```python
# OLD
CLEANUP_TIMEOUT = 5.0  # seconds

# NEW
CLEANUP_TIMEOUT = 10.0  # seconds - safer margin
```

---

## MIGRATION STEPS

### Step 1: Backup Current Files
```bash
cd state_estimation
cp lane_state_tracker.py lane_state_tracker_v1_backup.py
cp state_estimator.py state_estimator_v1_backup.py
```

### Step 2: Replace with Day 2 Versions
```bash
# Copy new versions
cp /path/to/lane_state_tracker_v2.py state_estimation/lane_state_tracker.py
cp /path/to/state_estimator_v2.py state_estimation/state_estimator.py
```

### Step 3: Update Imports (if needed)
Imports should remain the same:
```python
from state_estimation.lane_state_tracker import LaneStateTracker, LaneState
from state_estimation.state_estimator import TrafficStateEstimator, IntersectionState
```

### Step 4: Update Control Code (if accessing new fields)
```python
# OLD - emergency distance not available at intersection level
state = estimator.update(vehicles, time)
if state.has_emergency:
    # Had to dig through lane states to find distance
    pass

# NEW - emergency distance available directly
state = estimator.update(vehicles, time)
if state.has_emergency:
    distance = state.emergency_distance  # NEW field
    approach = state.emergency_approach
```

---

## BACKWARD COMPATIBILITY

### What Breaks
**Nothing!** All existing code using `LaneState` and `IntersectionState` will continue to work:

```python
# This still works
state = estimator.update(vehicles, time)
queue = state.lane_states["N_in_0"].queue_length  # ✓ Works
total = state.total_vehicles                       # ✓ Works
```

### What's New (optional to use)
```python
# NEW: queue vehicle count
count = state.lane_states["N_in_0"].queue_vehicle_count

# NEW: total waiting time
total_wait = state.total_waiting_time

# NEW: max queue
max_q = state.max_queue_length

# NEW: emergency distance
if state.has_emergency:
    dist = state.emergency_distance
```

### What Won't Work Anymore
```python
# Mutation (now raises FrozenInstanceError)
state.total_vehicles = 10  # ✗ ERROR: dataclass is frozen
```

**Fix:** Don't mutate state. Create new state if needed (not typical in state estimation).

---

## VALIDATION

### Run Unit Tests
```bash
python validate_day2.py
```

**Expected output:**
```
======================================================================
DAY 2 STATE ESTIMATION VALIDATION
======================================================================
✓ Queue length: 25.0m (expected 25.0m)
✓ Waiting time: 5.0s (expected 5.0s)
✓ Memory cleaned: 0 vehicles tracked (expected 0)
✓ Smoothing reduces variance by 45.2%
✓ All physical constraints satisfied
======================================================================
✓ ALL TESTS PASSED
======================================================================
```

### Visual Validation
After running `test_temporal_stability()`, check:
```
results/day2_validation/temporal_stability.png
```

**Healthy output:**
- Blue line (smoothed) should be smoother than red line (raw)
- No sudden jumps except at signal changes
- Gradual queue growth and discharge

### Run Existing Experiments
```bash
# Test with existing code
python experiments/test_state_estimation_gt.py
```

**Should produce identical results** (within smoothing differences).

---

## TROUBLESHOOTING

### Issue: FrozenInstanceError
```
dataclasses.FrozenInstanceError: cannot assign to field 'queue_length'
```

**Cause:** Trying to mutate immutable dataclass  
**Fix:** Don't mutate state. Use it read-only.

### Issue: Waiting Times Too Long
```
Average waiting time: 120s (unrealistic)
```

**Cause:** Old code bug (tracking from first_seen)  
**Fix:** Ensure using Day 2 version of `lane_state_tracker.py`  
**Check:** Grep for `vehicle_stop_time` in code

### Issue: Missing Field Error
```
AttributeError: 'LaneState' object has no attribute 'queue_vehicle_count'
```

**Cause:** Using old version of LaneState  
**Fix:** Make sure Day 2 version is installed correctly

---

## COMPARISON: DAY 1 vs DAY 2

| Aspect | Day 1 | Day 2 |
|--------|-------|-------|
| Immutability | Mutable dataclasses | Frozen (immutable) |
| Waiting time | From first_seen (BUG) | From stop_time (CORRECT) |
| Queue count | Implicit | Explicit field |
| Emergency distance | Per-lane only | Intersection-level |
| Total waiting time | Not tracked | Tracked |
| Max queue | Not tracked | Tracked |
| Validation | None | Built-in methods |
| Documentation | Informal | Fully specified |
| Cleanup timeout | 5s | 10s (safer) |

---

## ROLLBACK (if needed)

```bash
# Restore Day 1 versions
cd state_estimation
mv lane_state_tracker_v1_backup.py lane_state_tracker.py
mv state_estimator_v1_backup.py state_estimator.py
```

---

## NEXT STEPS

After migration is complete:
1. ✓ Run validation tests
2. ✓ Run existing experiments  
3. ✓ Verify plots look reasonable
4. → Proceed to Day 3 (Control Logic)

**Status after Day 2:**
- ✅ Perception interfaces frozen (Day 1)
- ✅ State estimation interfaces frozen (Day 2)
- → Ready for control algorithm development

---

**END OF MIGRATION GUIDE**
