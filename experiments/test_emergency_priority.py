"""
Test emergency vehicle priority system.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from perception.sumo_adapter import SumoPerceptionAdapter
from perception.lane_mapper import LaneMapper
from state_estimation.state_estimator import TrafficStateEstimator
from control.signal_controller import IntegratedSignalController
import matplotlib.pyplot as plt
import numpy as np


def main():
    print("="*70)
    print("Emergency Vehicle Priority System Test")
    print("="*70)
    
    # Setup
    config_file = project_root / "sumo_networks" / "simple_4way" / "sumo.cfg"
    intersection_config = project_root / "config" / "intersection_config.yaml"
    output_dir = project_root / "results" / "emergency_priority"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n1. Initializing components...")
    sumo = SUMOInterface(str(config_file), use_gui=False)
    sumo.start()
    
    lane_mapper = LaneMapper(str(intersection_config))
    perception = SumoPerceptionAdapter(sumo, lane_mapper)
    
    lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    state_estimator = TrafficStateEstimator(lane_ids, enable_smoothing=True)
    
    # Integrated controller with emergency priority
    controller = IntegratedSignalController()
    
    print("\n" + "="*70)
    print("Running emergency vehicle scenario...")
    print("="*70 + "\n")
    
    # Metrics collection
    metrics = {
        'time': [],
        'mode': [],  # 0 = normal, 1 = emergency
        'emergency_distance': [],
        'N_queue': [],
        'S_queue': [],
        'E_queue': [],
        'W_queue': []
    }
    
    emergency_added = False
    emergency_detected_time = None
    emergency_cleared_time = None
    
    try:
        for step in range(600):  # 60 seconds
            sumo.step()
            current_time = sumo.get_current_time()
            
            # Add emergency vehicle at 20 seconds
            if not emergency_added and current_time >= 20.0:
                print("\n" + "="*70)
                print("🚨 SPAWNING EMERGENCY VEHICLE (Ambulance from North)")
                print("="*70 + "\n")
                sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
                emergency_added = True
            
            # Perception & state
            perceived = perception.perceive(current_time)
            state = state_estimator.update(perceived, current_time)
            
            # Control with emergency priority
            signal_state = controller.update(state, current_time)
            sumo.set_traffic_light_state(signal_state)
            
            # Get controller status
            status = controller.get_status()
            
            # Track emergency detection
            if status['mode'] == 'EMERGENCY' and emergency_detected_time is None:
                emergency_detected_time = current_time
                print(f"\n⚡ Emergency detected at t={current_time:.1f}s")
            
            if emergency_detected_time and not status['emergency_active'] and emergency_cleared_time is None:
                emergency_cleared_time = current_time
                print(f"✓ Emergency cleared at t={current_time:.1f}s")
                print(f"  Total preemption time: {current_time - emergency_detected_time:.1f}s\n")
            
            # Collect metrics
            if step % 10 == 0:  # Every second
                metrics['time'].append(current_time)
                metrics['mode'].append(1 if status['mode'] == 'EMERGENCY' else 0)
                
                # Emergency distance
                if status['emergency_distance']:
                    metrics['emergency_distance'].append(status['emergency_distance'])
                else:
                    metrics['emergency_distance'].append(None)
                
                # Queue lengths
                for approach in ['N', 'S', 'E', 'W']:
                    queue = state.approach_metrics[approach]['total_queue_length']
                    metrics[f'{approach}_queue'].append(queue)
            
            # Print status every 2 seconds
            if step % 20 == 0:
                mode_str = "🚨 EMERGENCY" if status['mode'] == 'EMERGENCY' else "✓ NORMAL"
                print(f"t={current_time:5.1f}s | Mode: {mode_str:15s} | "
                      f"Vehicles: {state.total_vehicles:3d} | "
                      f"Emergency State: {status['emergency_state']:12s}")
                
                if status['emergency_distance']:
                    print(f"           Emergency distance: {status['emergency_distance']:.1f}m")
        
        # Generate plots
        print("\n" + "="*70)
        print("Generating analysis plots...")
        print("="*70 + "\n")
        
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        fig.suptitle('Emergency Vehicle Priority System Performance', fontsize=16)
        
        # Plot 1: Mode and emergency distance
        ax1 = axes[0]
        ax1_mode = ax1.twinx()
        
        # Plot emergency distance
        emergency_times = []
        emergency_dists = []
        for t, d in zip(metrics['time'], metrics['emergency_distance']):
            if d is not None:
                emergency_times.append(t)
                emergency_dists.append(d)
        
        if emergency_times:
            ax1.plot(emergency_times, emergency_dists, 'r-', linewidth=3, label='Emergency Distance')
            ax1.axhline(y=80, color='orange', linestyle='--', label='Preemption Threshold (80m)')
            ax1.axhline(y=5, color='green', linestyle='--', label='Clearing Threshold (5m)')
        
        # Plot mode
        ax1_mode.fill_between(metrics['time'], 0, metrics['mode'], 
                             alpha=0.3, color='red', label='Emergency Mode Active')
        
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Emergency Vehicle Distance (m)', color='r')
        ax1_mode.set_ylabel('Mode (0=Normal, 1=Emergency)', color='red')
        ax1.set_title('Emergency Detection and Distance')
        ax1.legend(loc='upper left')
        ax1_mode.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='y', labelcolor='r')
        
        # Plot 2: Queue lengths during emergency
        ax2 = axes[1]
        for approach in ['N', 'S', 'E', 'W']:
            ax2.plot(metrics['time'], metrics[f'{approach}_queue'], 
                    linewidth=2, label=f'{approach} Approach')
        
        # Highlight emergency period
        if emergency_detected_time and emergency_cleared_time:
            ax2.axvspan(emergency_detected_time, emergency_cleared_time, 
                       alpha=0.2, color='red', label='Emergency Preemption')
        
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Queue Length (m)')
        ax2.set_title('Queue Dynamics During Emergency')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: N vs E comparison (emergency corridor vs conflicting)
        ax3 = axes[2]
        ax3.plot(metrics['time'], metrics['N_queue'], 
                'b-', linewidth=2, label='North (Emergency Corridor)')
        ax3.plot(metrics['time'], metrics['E_queue'], 
                'r-', linewidth=2, label='East (Conflicting Direction)')
        
        if emergency_detected_time and emergency_cleared_time:
            ax3.axvspan(emergency_detected_time, emergency_cleared_time, 
                       alpha=0.2, color='red')
        
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('Queue Length (m)')
        ax3.set_title('Emergency Corridor vs Conflicting Direction')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        plot_path = output_dir / "emergency_priority_analysis.png"
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved: {plot_path}")
        
        # Summary statistics
        print(f"\n{'='*70}")
        print("EMERGENCY PRIORITY PERFORMANCE SUMMARY")
        print(f"{'='*70}")
        
        if emergency_detected_time and emergency_cleared_time:
            response_time = emergency_detected_time - 20.0  # Time from spawn to detection
            preemption_duration = emergency_cleared_time - emergency_detected_time
            
            print(f"  Emergency spawned at:     t=20.0s")
            print(f"  Emergency detected at:    t={emergency_detected_time:.1f}s")
            print(f"  Emergency cleared at:     t={emergency_cleared_time:.1f}s")
            print(f"  Detection response time:  {response_time:.1f}s")
            print(f"  Total preemption duration: {preemption_duration:.1f}s")
        
        print(f"\n✓ Emergency priority test complete!")
        print(f"{'='*70}\n")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    finally:
        sumo.close()


if __name__ == "__main__":
    main()
