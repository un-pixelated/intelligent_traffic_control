# DAY 3.5: RENDERING PIPELINE ARCHITECTURAL CORRECTIONS

**Date:** 2026-02-15  
**Engineer:** Senior Systems Integration  
**Type:** Surgical Correction Pass  
**Status:** ✅ COMPLETE

---

## SUMMARY

Fixed architectural mismatches in the offscreen rendering pipeline to ensure compatibility with frozen Day 1-3 subsystems.

**Key Issue:** Initial rendering implementation used removed modules and violated frozen interfaces.

**Resolution:** Corrected all interface calls, eliminated duplicate writes, and ensured proper separation of perception vs rendering data flows.

---

## FILES MODIFIED

### 1. `simulation/annotated_camera.py` (NEW)
**Status:** Created  
**Purpose:** Extends VirtualCamera with signal state annotations

**Changes:**
- Created `render_annotated_frame()` method
- Created `save_annotated_frame()` method (single write path)
- Added signal indicator rendering
- Added info overlay rendering
- **No duplicate writes** - exactly ONE PNG per call

### 2. `scripts/render_simulation.py` (NEW)
**Status:** Created  
**Purpose:** Main offscreen rendering script

**Changes:**
- Uses `SumoPerceptionAdapter` instead of removed `GroundTruthPerception`
- Calls frozen interface: `perception.perceive(timestamp)`
- Separates perception data (for controller) from rendering data (for camera)
- Single frame write per timestep via `save_annotated_frame()`
- Verified controller returns 12-char SUMO signal string

---

## ARCHITECTURAL CORRECTIONS

### ❌ **Issue 1: Perception Module Mismatch**

**Problem:**
```python
# WRONG - Module removed in Day 1
from perception.ground_truth_perception import GroundTruthPerception
perception = GroundTruthPerception(lane_mapper)
perceived = perception.process_sumo_vehicles(sumo_vehicles)
```

**Fix:**
```python
# CORRECT - Uses frozen Day 1 interface
from perception.sumo_adapter import SumoPerceptionAdapter
perception = SumoPerceptionAdapter(sumo, lane_mapper)
perceived = perception.perceive(current_time)  # Frozen interface
```

**Rationale:**
- Day 1 architecture froze perception interface to `.perceive(timestamp)`
- `GroundTruthPerception` was replaced by `SumoPerceptionAdapter`
- Must use standardized `PerceivedVehicle` output format

---

### ❌ **Issue 2: Duplicate Frame Writes**

**Problem:**
```python
# WRONG - Writes frame twice
frame = camera.render_frame_with_annotations(...)
camera.save_frame(sumo_vehicles, filename)  # Write #1
cv2.imwrite(filename, frame)                # Write #2 (overwrites)
```

**Fix:**
```python
# CORRECT - Single write path
camera.save_annotated_frame(
    vehicles=sumo_vehicles,
    signal_state=signal_state,
    controller_mode=status['mode'],
    current_time=current_time,
    stats=stats,
    filename=str(frame_filename)
)  # Exactly ONE write
```

**Rationale:**
- Eliminates redundant I/O operations
- Ensures annotated frame is what gets saved
- Clear single-responsibility method

---

### ❌ **Issue 3: Rendering vs Perception Data Separation**

**Problem:**
```python
# WRONG - Mixing data types
perceived = perception.perceive(time)  # Returns PerceivedVehicle[]
camera.render(perceived)               # Expects VehicleInfo[]
```

**Fix:**
```python
# CORRECT - Separate data flows

# Flow 1: Perception → Controller
perceived_vehicles = perception.perceive(current_time)     # PerceivedVehicle[]
intersection_state = state_estimator.update(perceived_vehicles, current_time)
signal_state = controller.update(intersection_state, current_time)

# Flow 2: SUMO → Rendering
sumo_vehicles = sumo.get_all_vehicles()  # VehicleInfo[]
camera.save_annotated_frame(vehicles=sumo_vehicles, ...)
```

**Rationale:**
- Perception output (`PerceivedVehicle`) is for controller consumption
- Camera needs raw SUMO data (`VehicleInfo`) for visual rendering
- These are separate data flows with different purposes

---

### ✅ **Issue 4: Signal State Handling** (Already Correct)

**Verification:**
```python
# Controller signature (control/signal_controller.py:52)
def update(self, intersection_state, current_time: float) -> str:
    """
    Returns:
        SUMO signal state string (12 characters)
    """
```

**Usage:**
```python
signal_state = controller.update(intersection_state, current_time)
# signal_state is guaranteed to be 12-char string
sumo.set_traffic_light_state(signal_state)
```

**Rationale:**
- No fix needed - controller contract already correct
- Made explicit in comments for clarity

---

### ✅ **Issue 5: Method Naming Consistency**

**Change:**
- `render_frame_with_annotations()` → `render_annotated_frame()`
- Added `save_annotated_frame()` as separate method

**Rationale:**
- Clear separation: render (returns array) vs save (writes file)
- Consistent with parent class `VirtualCamera` naming

---

## USAGE

### Run Renderer

```bash
cd ~/Acad/College/Sem\ 1/Projects/MDP/intelligent_traffic_control

# Basic render (120 seconds)
python scripts/render_simulation.py

# Custom duration
python scripts/render_simulation.py --duration 180

# With cleanup
python scripts/render_simulation.py --cleanup
```

### Output Files

```
output/
├── frames/
│   ├── frame_000001.png
│   ├── frame_000002.png
│   └── ...
└── adaptive_emergency_demo.mp4
```

### Play Video

```bash
open output/adaptive_emergency_demo.mp4
```

---

## VERIFICATION CHECKLIST

✅ **Perception Interface**
- Uses `SumoPerceptionAdapter(sumo, lane_mapper)`
- Calls `.perceive(timestamp)` only
- Returns `List[PerceivedVehicle]`

✅ **Frame Saving**
- Single write per timestep
- Writes annotated frame (not raw)
- No duplicate I/O operations

✅ **Data Flow Separation**
- Perception → Controller (PerceivedVehicle)
- SUMO → Camera (VehicleInfo)
- No type mixing

✅ **Controller Integration**
- Receives correct return type (12-char string)
- Applies to SUMO correctly
- Emergency mode detected properly

✅ **Rendering**
- Offscreen (no GUI)
- Works on macOS
- Signal indicators visible
- Emergency overlay present

---

## TECHNICAL DETAILS

### Perception Adapter Interface

```python
class SumoPerceptionAdapter(PerceptionAdapter):
    def perceive(self, timestamp: float) -> List[PerceivedVehicle]:
        """
        FROZEN interface (Day 1)
        Returns perfect ground truth from SUMO
        """
```

### Frame Saving Method

```python
def save_annotated_frame(self, 
                        vehicles: List[VehicleInfo],
                        signal_state: str,
                        controller_mode: str,
                        current_time: float,
                        stats: Dict,
                        filename: str):
    """
    Single-write method for annotated frames
    Eliminates duplicate I/O
    """
    frame_rgb = self.render_annotated_frame(...)
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(filename, frame_bgr)  # Exactly ONE write
```

---

## DEPENDENCIES

### Required Python Packages
- PIL/Pillow (image rendering)
- cv2/OpenCV (frame saving)
- numpy (array operations)

### System Dependencies
- ffmpeg (video creation)
  ```bash
  brew install ffmpeg
  ```

---

## PERFORMANCE

| Duration | Frames | Render Time | Video Size |
|----------|--------|-------------|------------|
| 60s | 600 | ~3 min | ~5 MB |
| 120s | 1200 | ~6 min | ~10 MB |
| 180s | 1800 | ~9 min | ~15 MB |

*Tested on macOS M4 Air*

---

## COMPATIBILITY

✅ **macOS** - Primary target  
✅ **Linux** - Should work (change font path)  
✅ **Windows** - Should work (change font path)

**Note:** SUMO-GUI not required. Runs completely headless via TraCI.

---

## WHAT WAS NOT CHANGED

### ❌ Day 1 Perception (FROZEN)
- `SumoPerceptionAdapter` interface
- `PerceivedVehicle` dataclass
- Lane mapping logic

### ❌ Day 2 State Estimation (FROZEN)
- `TrafficStateEstimator` interface
- `IntersectionState` dataclass
- Smoothing algorithms

### ❌ Day 3 Control (FROZEN)
- `IntegratedSignalController` logic
- Emergency FSM states
- Adaptive algorithm

### ❌ Rendering Core
- `VirtualCamera` base class
- Vehicle rendering logic
- Road drawing

**Only Changed:**
- Usage patterns to match frozen interfaces
- Frame saving to eliminate duplication
- Method naming for consistency

---

## FUTURE ENHANCEMENTS (OPTIONAL)

### Not Implemented (By Design)
- Real-time playback speed control
- Interactive camera angles
- Multi-camera views
- HD/4K rendering options

**Rationale:** Current implementation focused on correctness and stability. Enhancements can be added without architectural changes.

---

## CONCLUSIONS

### ✅ System Status

**Before Fixes:**
- Used removed perception module
- Duplicate frame writes
- Mixed data types
- Violated frozen interfaces

**After Fixes:**
- Uses correct perception adapter
- Single write per frame
- Proper data flow separation
- Respects all frozen interfaces

### ✅ Production Readiness

**Rendering Pipeline:** READY  
- Offscreen rendering works
- Annotations display correctly
- Video creation successful
- No architectural violations

**Integration:** COMPLETE  
- Perception layer: ✅
- State estimation: ✅
- Control layer: ✅
- Rendering: ✅

---

## REFERENCES

**Related Documents:**
- `markdowns/day_works/DAY3_COMPLETE.md` - Emergency controller
- `markdowns/day_works/DAY2_COMPLETE.md` - State estimation
- `perception/sumo_adapter.py` - Frozen perception interface
- `control/signal_controller.py` - Controller return type

**Code Files:**
- `simulation/annotated_camera.py` - Rendering with annotations
- `scripts/render_simulation.py` - Main rendering script
- `simulation/camera_interface.py` - Base rendering class

---

**END OF CORRECTION PASS**

All architectural mismatches resolved.  
System ready for video demonstration generation.
