"""
Test YOLOv8 detection and ByteTrack tracking on SUMO simulation.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from simulation.camera_interface import VirtualCamera
from perception.detector import VehicleDetector
from perception.tracker import ByteTracker
import cv2
import numpy as np


def main():
    print("="*70)
    print("Testing Perception Pipeline: Detection + Tracking")
    print("="*70)
    
    # Paths
    config_file = project_root / "sumo_networks" / "simple_4way" / "sumo.cfg"
    output_dir = project_root / "results" / "perception_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    print("\n1. Initializing SUMO...")
    sumo = SUMOInterface(str(config_file), use_gui=False)
    sumo.start()
    
    print("2. Initializing camera...")
    camera = VirtualCamera(
        image_size=(1280, 720),
        view_range=150.0,
        intersection_center=sumo.intersection_pos
    )
    
    print("3. Loading YOLOv8 detector...")
    detector = VehicleDetector(model_name='yolov8n.pt', device='mps')
    
    print("4. Initializing ByteTrack tracker...")
    tracker = ByteTracker(track_thresh=0.5, track_buffer=30, match_thresh=0.8)
    
    print("\n" + "="*70)
    print("Running simulation with perception...")
    print("="*70 + "\n")
    
    try:
        for step in range(200):  # Run for 20 seconds
            sumo.step()
            
            # Get vehicles and render frame
            vehicles = sumo.get_all_vehicles()
            frame = camera.render_frame(vehicles)
            
            # Detect vehicles
            detections = detector.detect(frame, conf_threshold=0.3)
            
            # Track vehicles
            tracks = tracker.update(detections)
            
            # Print status every 2 seconds
            if step % 20 == 0:
                sim_time = sumo.get_current_time()
                print(f"t={sim_time:.1f}s | SUMO vehicles: {len(vehicles):2d} | "
                      f"Detections: {len(detections):2d} | Active tracks: {len(tracks):2d}")
                
                # Visualize every 2 seconds
                frame_vis = frame.copy()
                
                # Draw tracks
                for track in tracks:
                    x1, y1, x2, y2 = [int(v) for v in track.bbox]
                    
                    # Color based on track age
                    if track.hits < 5:
                        color = (255, 255, 0)  # Yellow = new track
                    else:
                        color = (0, 255, 0)  # Green = stable track
                    
                    # Draw bbox
                    cv2.rectangle(frame_vis, (x1, y1), (x2, y2), color, 2)
                    
                    # Draw track ID and info
                    label = f"ID:{track.track_id} {track.class_name}"
                    cv2.putText(frame_vis, label, (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    
                    # Draw velocity arrow
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    vel_x, vel_y = track.velocity
                    arrow_scale = 3
                    end_x = int(center_x + vel_x * arrow_scale)
                    end_y = int(center_y + vel_y * arrow_scale)
                    cv2.arrowedLine(frame_vis, (center_x, center_y), 
                                   (end_x, end_y), (255, 0, 255), 2)
                
                # Save frame
                output_path = output_dir / f"tracked_{step:04d}.png"
                cv2.imwrite(str(output_path), cv2.cvtColor(frame_vis, cv2.COLOR_RGB2BGR))
                print(f"  Saved: {output_path.name}")
            
            # Add emergency vehicle at 10 seconds
            if step == 100:
                print("\n🚨 Adding emergency vehicle...")
                sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
                print()
        
        print("\n" + "="*70)
        print("✓ Perception test complete!")
        print(f"✓ Frames saved to: {output_dir}")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted")
    finally:
        sumo.close()


if __name__ == "__main__":
    main()
