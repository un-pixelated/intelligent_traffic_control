"""
Test state estimation with SUMO ground truth (no vision).
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from perception.sumo_adapter import SumoPerceptionAdapter
from perception.lane_mapper import LaneMapper
from state_estimation.state_estimator import TrafficStateEstimator
import matplotlib.pyplot as plt
import numpy as np


def main():
    print("="*70)
    print("Testing State Estimation with Ground Truth")
    print("="*70)
    
    # Paths
    config_file = project_root / "sumo_networks" / "simple_4way" / "sumo.cfg"
    intersection_config = project_root / "config" / "intersection_config.yaml"
    output_dir = project_root / "results" / "state_estimation_gt"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize
    print("\n1. Initializing SUMO...")
    sumo = SUMOInterface(str(config_file), use_gui=False)
    sumo.start()
    
    print("2. Initializing ground truth perception...")
    lane_mapper = LaneMapper(str(intersection_config))
    perception = SumoPerceptionAdapter(sumo, lane_mapper)
    
    print("3. Initializing state estimator...")
    lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    state_estimator = TrafficStateEstimator(lane_ids, enable_smoothing=True)
    
    print("\n" + "="*70)
    print("Running simulation...")
    print("="*70 + "\n")
    
    # Data collection
    time_series = {
        'time': [],
        'N_queue': [], 'S_queue': [], 'E_queue': [], 'W_queue': [],
        'N_vehicles': [], 'S_vehicles': [], 'E_vehicles': [], 'W_vehicles': [],
        'total_vehicles': [],
        'total_stopped': []
    }
    
    try:
        for step in range(400):  # 40 seconds
            sumo.step()
            current_time = sumo.get_current_time()
            
            # Get ground truth vehicles from SUMO via perception adapter
            perceived_vehicles = perception.perceive(current_time)
            
            # State estimation
            intersection_state = state_estimator.update(perceived_vehicles, current_time)
            
            # Collect data
            time_series['time'].append(current_time)
            for approach in ['N', 'S', 'E', 'W']:
                metrics = intersection_state.approach_metrics[approach]
                time_series[f'{approach}_queue'].append(metrics['total_queue_length'])
                time_series[f'{approach}_vehicles'].append(metrics['total_vehicles'])
            
            time_series['total_vehicles'].append(intersection_state.total_vehicles)
            time_series['total_stopped'].append(intersection_state.total_stopped)
            
            # Print every 5 seconds
            if step % 50 == 0:
                state_estimator.print_summary(intersection_state)
            
            # Add emergency vehicle
            if step == 200:
                print("\n🚨 Adding emergency vehicle...\n")
                sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
        
        # Plot results
        print("\nGenerating plots...")
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Traffic State Estimation (Ground Truth)', fontsize=16)
        
        # Queue lengths
        ax = axes[0, 0]
        for approach in ['N', 'S', 'E', 'W']:
            ax.plot(time_series['time'], time_series[f'{approach}_queue'], 
                   label=f'{approach}', linewidth=2)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Queue Length (m)')
        ax.set_title('Queue Length by Approach')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Vehicle counts
        ax = axes[0, 1]
        ax.plot(time_series['time'], time_series['total_vehicles'], 
               'b-', linewidth=2, label='Total')
        ax.plot(time_series['time'], time_series['total_stopped'], 
               'r-', linewidth=2, label='Stopped')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Count')
        ax.set_title('Vehicle Counts')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Per-approach vehicles
        ax = axes[1, 0]
        for approach in ['N', 'S', 'E', 'W']:
            ax.plot(time_series['time'], time_series[f'{approach}_vehicles'], 
                   label=f'{approach}', linewidth=2)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Vehicles')
        ax.set_title('Vehicles by Approach')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # N vs S comparison
        ax = axes[1, 1]
        ax.plot(time_series['time'], time_series['N_queue'], 
               'b-', linewidth=2, label='North Queue')
        ax.plot(time_series['time'], time_series['S_queue'], 
               'r-', linewidth=2, label='South Queue')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Queue Length (m)')
        ax.set_title('North vs South')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plot_path = output_dir / "state_results_gt.png"
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved: {plot_path}")
        
        # Statistics
        print(f"\nStatistics:")
        print(f"  Avg vehicles: {np.mean(time_series['total_vehicles']):.1f}")
        print(f"  Peak vehicles: {np.max(time_series['total_vehicles'])}")
        for approach in ['N', 'S', 'E', 'W']:
            avg_queue = np.mean(time_series[f'{approach}_queue'])
            avg_vehicles = np.mean(time_series[f'{approach}_vehicles'])
            print(f"  {approach}: {avg_vehicles:.1f} veh, {avg_queue:.1f}m queue")
        
        print("\n" + "="*70)
        print("✓ Test complete!")
        print("="*70)
        
    finally:
        sumo.close()


if __name__ == "__main__":
    main()
