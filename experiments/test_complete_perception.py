"""
Test complete perception pipeline with lane assignment and distance estimation.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from simulation.camera_interface import VirtualCamera
from perception.perception_pipeline import PerceptionPipeline
import cv2
import numpy as np


def main():
    print("="*70)
    print("Testing Complete Perception Pipeline")
    print("="*70)
    
    # Paths
    config_file = project_root / "sumo_networks" / "simple_4way" / "sumo.cfg"
    intersection_config = project_root / "config" / "intersection_config.yaml"
    output_dir = project_root / "results" / "complete_perception"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize SUMO
    print("\n1. Initializing SUMO...")
    sumo = SUMOInterface(str(config_file), use_gui=False)
    sumo.start()
    
    # Initialize camera
    print("2. Initializing camera...")
    camera = VirtualCamera(
        image_size=(1280, 720),
        view_range=150.0,
        intersection_center=sumo.intersection_pos
    )
    
    # Initialize perception pipeline
    print("3. Initializing perception pipeline...")
    pipeline = PerceptionPipeline(
        config_path=str(intersection_config),
        camera_scale=camera.scale,
        intersection_center=camera.intersection_center,
        model_name='yolov8n.pt',
        device='mps'
    )
    
    print("\n" + "="*70)
    print("Running simulation...")
    print("="*70 + "\n")
    
    # Statistics
    lane_counts = {}
    
    try:
        for step in range(300):  # 30 seconds
            sumo.step()
            
            # Get vehicles and render
            vehicles = sumo.get_all_vehicles()
            frame = camera.render_frame(vehicles)
            
            # Process through perception pipeline
            perceived_vehicles = pipeline.process_frame(
                frame, 
                image_center=(camera.image_size[0]//2, camera.image_size[1]//2)
            )
            
            # Update statistics
            for pv in perceived_vehicles:
                if pv.lane_id:
                    lane_counts[pv.lane_id] = lane_counts.get(pv.lane_id, 0) + 1
            
            # Print status every 2 seconds
            if step % 20 == 0:
                sim_time = sumo.get_current_time()
                print(f"\nt={sim_time:.1f}s | Vehicles: {len(perceived_vehicles)}")
                
                # Group by approach
                by_approach = {}
                emergency_count = 0
                
                for pv in perceived_vehicles:
                    if pv.is_emergency:
                        emergency_count += 1
                    
                    if pv.lane_id:
                        approach = pv.lane_id.split('_')[0]
                        if approach not in by_approach:
                            by_approach[approach] = []
                        by_approach[approach].append(pv)
                
                # Print per-approach summary
                for approach in ['N', 'S', 'E', 'W']:
                    if approach in by_approach:
                        vehs = by_approach[approach]
                        avg_dist = np.mean([v.distance_to_stop_line for v in vehs])
                        print(f"  {approach}: {len(vehs)} vehicles, avg dist: {avg_dist:.1f}m")
                
                if emergency_count > 0:
                    print(f"  🚨 {emergency_count} EMERGENCY vehicles detected!")
                
                # Visualize
                frame_vis = pipeline.visualize(frame, perceived_vehicles)
                
                # Add text overlay
                cv2.putText(frame_vis, f"Time: {sim_time:.1f}s", (20, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(frame_vis, f"Vehicles: {len(perceived_vehicles)}", (20, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                # Save
                output_path = output_dir / f"perception_{step:04d}.png"
                cv2.imwrite(str(output_path), cv2.cvtColor(frame_vis, cv2.COLOR_RGB2BGR))
            
            # Add emergency vehicle
            if step == 150:
                print("\n🚨 Adding emergency vehicle...\n")
                sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
        
        print("\n" + "="*70)
        print("✓ Complete perception test finished!")
        print("\nLane statistics:")
        for lane_id, count in sorted(lane_counts.items()):
            print(f"  {lane_id}: {count} vehicle-frames")
        print(f"\n✓ Frames saved to: {output_dir}")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    finally:
        sumo.close()


if __name__ == "__main__":
    main()
