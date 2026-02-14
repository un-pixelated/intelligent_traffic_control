"""
Test and compare fixed-time vs adaptive controllers.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from perception.sumo_adapter import SumoPerceptionAdapter
from perception.lane_mapper import LaneMapper
from state_estimation.state_estimator import TrafficStateEstimator
from control.fixed_time_controller import FixedTimeController
from control.adaptive_controller import AdaptiveController
import matplotlib.pyplot as plt
import numpy as np


def run_experiment(controller, controller_name: str, duration: int = 300):
    """Run simulation with given controller"""
    print(f"\n{'='*70}")
    print(f"Testing: {controller_name}")
    print(f"{'='*70}\n")
    
    # Setup
    config_file = project_root / "sumo_networks" / "simple_4way" / "sumo.cfg"
    intersection_config = project_root / "config" / "intersection_config.yaml"
    
    sumo = SUMOInterface(str(config_file), use_gui=False)
    sumo.start()
    
    lane_mapper = LaneMapper(str(intersection_config))
    perception = SumoPerceptionAdapter(sumo, lane_mapper)
    
    lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    state_estimator = TrafficStateEstimator(lane_ids, enable_smoothing=True)
    
    # Metrics collection
    metrics = {
        'time': [],
        'total_waiting_time': [],
        'total_stopped': [],
        'avg_queue': [],
        'phase_changes': 0
    }
    
    last_phase_state = None
    
    try:
        for step in range(duration * 10):  # 0.1s per step
            sumo.step()
            current_time = sumo.get_current_time()
            
            # Perception & state estimation
            perceived = perception.perceive(current_time)
            state = state_estimator.update(perceived, current_time)
            
            # Control
            signal_state = controller.update(state, current_time)
            sumo.set_traffic_light_state(signal_state)
            
            # Track phase changes
            if last_phase_state != signal_state:
                metrics['phase_changes'] += 1
                last_phase_state = signal_state
            
            # Collect metrics every second
            if step % 10 == 0:
                metrics['time'].append(current_time)
                
                # Total waiting time
                total_wait = sum(
                    m['avg_waiting_time'] * m['total_vehicles']
                    for m in state.approach_metrics.values()
                )
                metrics['total_waiting_time'].append(total_wait)
                
                metrics['total_stopped'].append(state.total_stopped)
                
                # Average queue length
                avg_queue = np.mean([
                    m['total_queue_length']
                    for m in state.approach_metrics.values()
                ])
                metrics['avg_queue'].append(avg_queue)
            
            # Status every 10s
            if step % 100 == 0:
                print(f"t={current_time:5.1f}s | Vehicles: {state.total_vehicles:3d} | "
                      f"Stopped: {state.total_stopped:3d} | "
                      f"Avg Queue: {np.mean(metrics['avg_queue'][-10:]) if metrics['avg_queue'] else 0:.1f}m")
        
        print(f"\n{controller_name} Results:")
        print(f"  Total phase changes: {metrics['phase_changes']}")
        print(f"  Avg waiting time: {np.mean(metrics['total_waiting_time']):.1f}s")
        print(f"  Avg stopped vehicles: {np.mean(metrics['total_stopped']):.1f}")
        print(f"  Avg queue length: {np.mean(metrics['avg_queue']):.1f}m")
        
    finally:
        sumo.close()
    
    return metrics


def main():
    print("="*70)
    print("Controller Comparison Experiment")
    print("="*70)
    
    # Test fixed-time controller
    fixed_controller = FixedTimeController(ns_green_time=30, ew_green_time=30)
    fixed_metrics = run_experiment(fixed_controller, "Fixed-Time (30s/30s)", duration=300)
    
    # Test adaptive controller
    adaptive_controller = AdaptiveController(min_green=10, max_green=60)
    adaptive_metrics = run_experiment(adaptive_controller, "Adaptive (Webster)", duration=300)
    
    # Plot comparison
    print("\nGenerating comparison plots...")
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Fixed-Time vs Adaptive Controller Comparison', fontsize=16)
    
    # Waiting time
    ax = axes[0, 0]
    ax.plot(fixed_metrics['time'], fixed_metrics['total_waiting_time'], 
           'b-', linewidth=2, label='Fixed-Time')
    ax.plot(adaptive_metrics['time'], adaptive_metrics['total_waiting_time'], 
           'r-', linewidth=2, label='Adaptive')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Total Waiting Time (s)')
    ax.set_title('Total Waiting Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Stopped vehicles
    ax = axes[0, 1]
    ax.plot(fixed_metrics['time'], fixed_metrics['total_stopped'], 
           'b-', linewidth=2, label='Fixed-Time')
    ax.plot(adaptive_metrics['time'], adaptive_metrics['total_stopped'], 
           'r-', linewidth=2, label='Adaptive')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Stopped Vehicles')
    ax.set_title('Stopped Vehicles Over Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Average queue
    ax = axes[1, 0]
    ax.plot(fixed_metrics['time'], fixed_metrics['avg_queue'], 
           'b-', linewidth=2, label='Fixed-Time')
    ax.plot(adaptive_metrics['time'], adaptive_metrics['avg_queue'], 
           'r-', linewidth=2, label='Adaptive')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Average Queue Length (m)')
    ax.set_title('Average Queue Length')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Performance summary (bar chart)
    ax = axes[1, 1]
    metrics_names = ['Avg Wait\nTime (s)', 'Avg Stopped\nVehicles', 'Avg Queue\nLength (m)']
    fixed_values = [
        np.mean(fixed_metrics['total_waiting_time']),
        np.mean(fixed_metrics['total_stopped']),
        np.mean(fixed_metrics['avg_queue'])
    ]
    adaptive_values = [
        np.mean(adaptive_metrics['total_waiting_time']),
        np.mean(adaptive_metrics['total_stopped']),
        np.mean(adaptive_metrics['avg_queue'])
    ]
    
    x = np.arange(len(metrics_names))
    width = 0.35
    ax.bar(x - width/2, fixed_values, width, label='Fixed-Time', color='b', alpha=0.7)
    ax.bar(x + width/2, adaptive_values, width, label='Adaptive', color='r', alpha=0.7)
    ax.set_ylabel('Value')
    ax.set_title('Performance Summary (Lower is Better)')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics_names)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    output_dir = project_root / "results" / "controller_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "comparison.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"✓ Plot saved: {plot_path}")
    
    print("\n" + "="*70)
    print("✓ Controller comparison complete!")
    print("="*70)


if __name__ == "__main__":
    main()

