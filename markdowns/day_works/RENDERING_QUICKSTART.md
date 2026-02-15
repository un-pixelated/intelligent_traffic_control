# RENDERING SYSTEM - QUICK START

## Changes Made (Day 3.5)

### New Files
1. **simulation/annotated_camera.py** - Camera with signal/emergency annotations
2. **scripts/render_simulation.py** - Main rendering script
3. **markdowns/day_works/DAY3.5_RENDERING_FIXES.md** - Detailed documentation

### What Was Fixed
- ✅ Replaced removed `GroundTruthPerception` with `SumoPerceptionAdapter`
- ✅ Fixed duplicate frame writes (single write per timestep now)
- ✅ Separated perception data flow from rendering data flow
- ✅ Verified controller signal string handling
- ✅ All frozen interfaces respected (Days 1-3)

---

## Installation

### 1. Extract Files
```bash
unzip currentProject_fixed.zip
```

### 2. Install Dependencies
```bash
# System dependency
brew install ffmpeg

# Python packages (already in requirements.txt)
pip install opencv-python Pillow numpy
```

---

## Usage

### Run Rendering
```bash
cd intelligent_traffic_control

# Basic (120 seconds)
python scripts/render_simulation.py

# Custom duration
python scripts/render_simulation.py --duration 60

# With cleanup after video creation
python scripts/render_simulation.py --cleanup
```

### Output Location
```
output/
├── frames/           # Individual PNG frames
│   └── frame_*.png
└── adaptive_emergency_demo.mp4  # Final video
```

### View Video
```bash
open output/adaptive_emergency_demo.mp4
```

---

## What You'll See

- ✅ Top-down traffic simulation view
- ✅ **Signal lights** at each approach (N/S/E/W) - color changes with phase
- ✅ **Vehicle rendering** - cars (blue), ambulances (red)
- ✅ **Mode indicator** - "NORMAL" (green) or "EMERGENCY" (red)
- ✅ **Traffic stats** - vehicle count, stopped count
- ✅ **Emergency distance** - shown when ambulance detected

### Timeline
- **0-60s:** Normal traffic operation
- **60s:** 🚨 Emergency vehicle spawns (ambulance from North)
- **60-75s:** Emergency detection → signal override → path cleared
- **75-120s:** Return to normal operation

---

## Troubleshooting

### "ModuleNotFoundError: simulation.annotated_camera"
**Fix:** Make sure you extracted `simulation/annotated_camera.py` to the correct location

### "ffmpeg not found"
**Fix:** Install ffmpeg: `brew install ffmpeg`

### Frames render but video fails
**Fix:** Run ffmpeg manually:
```bash
cd output
ffmpeg -y -framerate 10 -i frames/frame_%06d.png \
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
  -movflags +faststart adaptive_emergency_demo.mp4
```

---

## Performance

| Duration | Est. Time | Output Size |
|----------|-----------|-------------|
| 60s | 3 min | ~5 MB |
| 120s | 6 min | ~10 MB |
| 180s | 9 min | ~15 MB |

---

## Technical Notes

### Perception Interface (FROZEN)
```python
perception = SumoPerceptionAdapter(sumo, lane_mapper)
perceived_vehicles = perception.perceive(current_time)
```

### Controller Interface (FROZEN)
```python
signal_state = controller.update(intersection_state, current_time)
# Returns: 12-character SUMO signal string
```

### Rendering (Separate from Perception)
```python
sumo_vehicles = sumo.get_all_vehicles()  # VehicleInfo[]
camera.save_annotated_frame(vehicles=sumo_vehicles, ...)
```

---

## File Locations

```
intelligent_traffic_control/
├── simulation/
│   ├── annotated_camera.py     ← NEW
│   ├── camera_interface.py     (existing)
│   └── sumo_interface.py       (existing)
├── scripts/
│   └── render_simulation.py    ← NEW
├── markdowns/
│   └── day_works/
│       └── DAY3.5_RENDERING_FIXES.md  ← NEW (detailed docs)
└── output/                     (auto-created)
    ├── frames/
    └── adaptive_emergency_demo.mp4
```

---

## Questions?

See detailed documentation:
- `markdowns/day_works/DAY3.5_RENDERING_FIXES.md`

Or run with verbose output:
```bash
python scripts/render_simulation.py --duration 120
```

---

**Status:** ✅ READY FOR DEMONSTRATION  
**Tested:** macOS M4 Air  
**Dependencies:** SUMO, Python 3.10+, ffmpeg
