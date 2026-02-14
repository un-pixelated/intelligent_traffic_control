"""
Test complete state estimation pipeline.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from simulation.camera_interface import VirtualCamera
from perception.perception_pipeline import PerceptionPipeline
from state_estimation.state_estimator import TrafficStateEstimator
import matplotlib.pyplot as plt
import numpy as np


def main():
    print("="*70)
    print("Testing Traffic State Estimation")
    print("="*70)
    
    # Paths
    config_file = project_root / "sumo_networks" / "simple_4way" / "sumo.cfg"
    intersection_config = project_root / "config" / "intersection_config.yaml"
    output_dir = project_root / "results" / "state_estimation"
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
    
    print("3. Initializing perception...")
    perception = PerceptionPipeline(
        config_path=str(intersection_config),
        camera_scale=camera.scale,
        intersection_center=camera.intersection_center,
        model_name='yolov8n.pt',
        device='mps'
    )
    
    print("4. Initializing state estimator...")
    # Get lane IDs from config
    lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    state_estimator = TrafficStateEstimator(lane_ids, enable_smoothing=True)
    
    print("\n" + "="*70)
    print("Running simulation with state estimation...")
    print("="*70 + "\n")
    
    # Data collection for plotting
    time_series = {
        'time': [],
        'N_queue': [],
        'S_queue': [],
        'E_queue': [],
        'W_queue': [],
        'total_vehicles': [],
        'total_stopped': []
    }
    
    try:
        for step in range(400):  # 40 seconds
            sumo.step()
            current_time = sumo.get_current_time()
            
            # Perception
            vehicles = sumo.get_all_vehicles()
            frame = camera.render_frame(vehicles)
            perceived_vehicles = perception.process_frame(
                frame, (camera.image_size[0]//2, camera.image_size[1]//2)
            )
            
            # State estimation
            intersection_state = state_estimator.update(perceived_vehicles, current_time)
            
            # Collect data
            time_series['time'].append(current_time)
            for approach in ['N', 'S', 'E', 'W']:
                time_series[f'{approach}_queue'].append(
                    intersection_state.approach_metrics[approach]['total_queue_length']
                )
            time_series['total_vehicles'].append(intersection_state.total_vehicles)
            time_series['total_stopped'].append(intersection_state.total_stopped)
            
            # Print summary every 5 seconds
            if step % 50 == 0:
                state_estimator.print_summary(intersection_state)
                
                # Print RL state vector
                rl_vector = state_estimator.get_state_vector_for_rl(intersection_state)
                print(f"RL State Vector: {rl_vector}")
                print()
            
            # Add emergency vehicle
            if step == 200:
                print("\n🚨 Adding emergency vehicle...\n")
                sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
        
        # Plot results
        print("\n" + "="*70)
        print("Generating plots...")
        print("="*70 + "\n")
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Traffic State Estimation Results', fontsize=16)
        
        # Queue lengths per approach
        ax = axes[0, 0]
        for approach in ['N', 'S', 'E', 'W']:
            ax.plot(time_series['time'], time_series[f'{approach}_queue'], 
                   label=f'{approach} Approach', linewidth=2)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Queue Length (m)')
        ax.set_title('Queue Length by Approach')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Total vehicles over time
        ax = axes[0, 1]
        ax.plot(time_series['time'], time_series['total_vehicles'], 
               'b-', linewidth=2, label='Total Vehicles')
        ax.plot(time_series['time'], time_series['total_stopped'], 
               'r-', linewidth=2, label='Stopped Vehicles')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Vehicle Count')
        ax.set_title('Vehicle Counts Over Time')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Queue comparison (N vs S)
        ax = axes[1, 0]
        ax.plot(time_series['time'], time_series['N_queue'], 
               'b-', linewidth=2, label='North')
        ax.plot(time_series['time'], time_series['S_queue'], 
               'r-', linewidth=2, label='South')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Queue Length (m)')
        ax.set_title('North vs South Queue Comparison')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Queue comparison (E vs W)
        ax = axes[1, 1]
        ax.plot(time_series['time'], time_series['E_queue'], 
               'g-', linewidth=2, label='East')
        ax.plot(time_series['time'], time_series['W_queue'], 
               'm-', linewidth=2, label='West')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Queue Length (m)')
        ax.set_title('East vs West Queue Comparison')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        plot_path = output_dir / "state_estimation_results.png"
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved: {plot_path}")
        
        # Summary statistics
        print(f"\nSummary Statistics:")
        print(f"  Average total vehicles: {np.mean(time_series['total_vehicles']):.1f}")
        print(f"  Peak total vehicles: {np.max(time_series['total_vehicles'])}")
        print(f"  Average queue (N): {np.mean(time_series['N_queue']):.1f}m")
        print(f"  Average queue (S): {np.mean(time_series['S_queue']):.1f}m")
        print(f"  Average queue (E): {np.mean(time_series['E_queue']):.1f}m")
        print(f"  Average queue (W): {np.mean(time_series['W_queue']):.1f}m")
        
        print("\n" + "="*70)
        print("✓ State estimation test complete!")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    finally:
        sumo.close()
        plt.close()


if __name__ == "__main__":
    main()
