"""
Live SUMO GUI demonstration.
Watch the traffic simulation and control decisions in real-time.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from perception.ground_truth_perception import GroundTruthPerception
from perception.lane_mapper import LaneMapper
from state_estimation.state_estimator import TrafficStateEstimator
from control.signal_controller import IntegratedSignalController
import time


def main():
    print("="*70)
    print(" LIVE TRAFFIC SIMULATION DEMO")
    print("="*70)
    print("\nThis will open SUMO GUI showing:")
    print("  • Real-time traffic flow")
    print("  • Signal state changes")
    print("  • Emergency vehicle (spawns at t=30s)")
    print("\nControls in SUMO GUI:")
    print("  • Click PLAY ▶ to start")
    print("  • Adjust speed with +/- buttons")
    print("  • Right-click vehicles for details")
    print("\nPress Enter to start...")
    input()
    
    # Paths
    config_file = str(project_root / "sumo_networks" / "simple_4way" / "sumo.cfg")
    intersection_config = str(project_root / "config" / "intersection_config.yaml")
    
    # Initialize components
    print("\nInitializing system...")
    
    # Use SUMO GUI (works on macOS via TraCI even if direct command doesn't)
    sumo = SUMOInterface(config_file, use_gui=True)
    
    # Try to start SUMO
    try:
        sumo.start()
    except Exception as e:
        print(f"\n⚠️  SUMO GUI failed to start: {e}")
        print("\nTrying alternative method...")
        print("Please open SUMO manually:")
        print(f"  1. Open 'SUMO sumo-gui' app from Applications")
        print(f"  2. File → Open Simulation → {config_file}")
        print(f"  3. Click Play")
        print("\nPress Ctrl+C when done\n")
        return
    
    lane_mapper = LaneMapper(intersection_config)
    perception = GroundTruthPerception(lane_mapper)
    
    lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    state_estimator = TrafficStateEstimator(lane_ids, enable_smoothing=True)
    
    controller = IntegratedSignalController()
    
    print("\n✓ System initialized")
    print("✓ SUMO GUI should be open now")
    print("\nSimulation starting in 3 seconds...")
    time.sleep(3)
    
    print("\nRunning simulation...")
    print("(Press Ctrl+C to stop)\n")
    
    emergency_spawned = False
    
    try:
        step = 0
        while True:
            sumo.step()
            current_time = sumo.get_current_time()
            
            # Spawn emergency vehicle at 30s
            if not emergency_spawned and current_time >= 30.0:
                print(f"\n{'='*70}")
                print(f"🚨 SPAWNING EMERGENCY VEHICLE (Ambulance from North)")
                print(f"{'='*70}\n")
                sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
                emergency_spawned = True
            
            # Perception & control
            sumo_vehicles = sumo.get_all_vehicles()
            perceived = perception.process_sumo_vehicles(sumo_vehicles)
            state = state_estimator.update(perceived, current_time)
            
            signal_state = controller.update(state, current_time)
            sumo.set_traffic_light_state(signal_state)
            
            # Status updates
            if step % 20 == 0:  # Every 2 seconds
                status = controller.get_status()
                mode_icon = "🚨" if status['mode'] == 'EMERGENCY' else "✓"
                
                print(f"t={current_time:5.1f}s {mode_icon} {status['mode']:10s} | "
                      f"Vehicles: {state.total_vehicles:3d} | "
                      f"Stopped: {state.total_stopped:3d}")
            
            step += 1
            time.sleep(0.05)  # Slow down for visibility
            
    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")
    finally:
        sumo.close()
        print("\n✓ Simulation complete")


if __name__ == "__main__":
    main()
