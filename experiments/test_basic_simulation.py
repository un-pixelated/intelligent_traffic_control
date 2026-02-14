"""
Test basic SUMO simulation and camera rendering.
Verifies installation and generates sample frames.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from simulation.camera_interface import VirtualCamera
import time


def main():
    # Path to SUMO config
    config_file = project_root / "sumo_networks" / "simple_4way" / "sumo.cfg"
    
    if not config_file.exists():
        print("✗ SUMO network not found. Run generate_network.py first!")
        return
    
    print("Starting SUMO simulation test...\n")
    
    # Initialize interface (use GUI to visualize)
    sumo = SUMOInterface(str(config_file), use_gui=False)
    sumo.start()
    
    # Initialize camera
    camera = VirtualCamera(
        image_size=(1280, 720),
        view_range=150.0,
        intersection_center=sumo.intersection_pos
    )
    
    # Create output directory
    output_dir = project_root / "data" / "synthetic_renders"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Running simulation for 10 seconds...\n")
    
    try:
        # Run for 100 steps (10 seconds at 0.1s per step)
        for step in range(100):
            sumo.step()
            
            # Get all vehicles
            vehicles = sumo.get_all_vehicles()
            
            # Print status every second
            if step % 10 == 0:
                sim_time = sumo.get_current_time()
                print(f"t={sim_time:.1f}s: {len(vehicles)} vehicles")
                
                # Render and save frame every second
                frame_path = output_dir / f"frame_{step:04d}.png"
                camera.save_frame(vehicles, str(frame_path))
                print(f"  Saved: {frame_path.name}")
            
            time.sleep(0.01)  # Small delay to see GUI
        
        # Add emergency vehicle
        print("\nAdding emergency vehicle...")
        sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
        
        # Run for another 100 steps
        for step in range(100, 200):
            sumo.step()
            
            vehicles = sumo.get_all_vehicles()
            
            if step % 10 == 0:
                sim_time = sumo.get_current_time()
                print(f"t={sim_time:.1f}s: {len(vehicles)} vehicles")
                
                # Check for emergency vehicles
                emergency = [v for v in vehicles if 'emergency' in v.type or 'ambulance' in v.id]
                if emergency:
                    print(f"  Emergency vehicle at distance: {emergency[0].distance_to_intersection:.1f}m")
            
            time.sleep(0.01)
        
        print("\n✓ Simulation complete!")
        print(f"✓ Frames saved to: {output_dir}")
        
    except KeyboardInterrupt:
        print("\nSimulation interrupted")
    finally:
        sumo.close()


if __name__ == "__main__":
    main()