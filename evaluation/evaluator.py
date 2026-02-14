"""
Complete evaluation framework for traffic control systems.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from perception.ground_truth_perception import GroundTruthPerception
from perception.lane_mapper import LaneMapper
from state_estimation.state_estimator import TrafficStateEstimator
from control.fixed_time_controller import FixedTimeController
from control.adaptive_controller import AdaptiveController
from control.signal_controller import IntegratedSignalController
from evaluation.metrics import MetricsCollector, PerformanceMetrics
from evaluation.scenarios import TrafficScenario
from typing import List
import time


class TrafficControlEvaluator:
    """Evaluates traffic control systems across multiple scenarios"""
    
    def __init__(self, config_file: str, intersection_config: str):
        self.config_file = config_file
        self.intersection_config = intersection_config
        
        # Setup components (initialized per run)
        self.lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
    
    def evaluate_controller(self, 
                          controller,
                          controller_name: str,
                          scenario: TrafficScenario,
                          verbose: bool = True) -> PerformanceMetrics:
        """
        Evaluate a controller on a scenario
        
        Args:
            controller: Controller instance
            controller_name: Name for logging
            scenario: Traffic scenario to run
            verbose: Print progress
            
        Returns:
            PerformanceMetrics object
        """
        if verbose:
            print(f"\n{'='*70}")
            print(f"Evaluating: {controller_name}")
            print(f"Scenario: {scenario.name} - {scenario.description}")
            print(f"Duration: {scenario.duration}s")
            print(f"{'='*70}\n")
        
        # Initialize simulation
        sumo = SUMOInterface(self.config_file, use_gui=False)
        sumo.start()
        
        # Perception and state estimation
        lane_mapper = LaneMapper(self.intersection_config)
        perception = GroundTruthPerception(lane_mapper)
        state_estimator = TrafficStateEstimator(self.lane_ids, enable_smoothing=True)
        
        # Metrics collector
        metrics_collector = MetricsCollector(controller_name)
        
        # Track emergency spawns
        spawned_emergencies = set()
        
        try:
            steps = int(scenario.duration * 10)  # 0.1s per step
            
            for step in range(steps):
                sumo.step()
                current_time = sumo.get_current_time()
                
                # Spawn emergency vehicles
                for event in scenario.emergency_events:
                    event_key = f"{event.spawn_time}_{event.route}"
                    if current_time >= event.spawn_time and event_key not in spawned_emergencies:
                        if verbose:
                            print(f"\n🚨 Spawning {event.vehicle_type} at t={current_time:.1f}s")
                        sumo.add_emergency_vehicle(
                            route_id=event.route,
                            vtype=event.vehicle_type
                        )
                        spawned_emergencies.add(event_key)
                
                # Perception
                sumo_vehicles = sumo.get_all_vehicles()
                perceived = perception.process_sumo_vehicles(sumo_vehicles)
                
                # State estimation
                intersection_state = state_estimator.update(perceived, current_time)
                
                # Control
                signal_state = controller.update(intersection_state, current_time)
                sumo.set_traffic_light_state(signal_state)
                
                # Get controller status (for emergency tracking)
                controller_status = None
                if hasattr(controller, 'get_status'):
                    controller_status = controller.get_status()
                
                # Collect metrics
                metrics_collector.update(
                    intersection_state,
                    signal_state,
                    current_time,
                    controller_status
                )
                
                # Progress reporting
                if verbose and step % 100 == 0:
                    progress = (step / steps) * 100
                    print(f"  Progress: {progress:5.1f}% | "
                          f"t={current_time:6.1f}s | "
                          f"Vehicles: {intersection_state.total_vehicles:3d}")
            
            # Finalize metrics
            metrics = metrics_collector.finalize(scenario.duration)
            
            if verbose:
                print(f"\n  ✓ Completed {controller_name} on {scenario.name}")
                self._print_metrics_summary(metrics)
            
            return metrics
            
        finally:
            sumo.close()
    
    def _print_metrics_summary(self, metrics: PerformanceMetrics):
        """Print summary of metrics"""
        print(f"\n  Results:")
        print(f"    Avg Waiting Time:     {metrics.avg_waiting_time:8.2f}s")
        print(f"    Avg Queue Length:     {metrics.avg_queue_length:8.2f}m")
        print(f"    Avg Stopped Vehicles: {metrics.avg_stopped_vehicles:8.2f}")
        print(f"    Phase Changes:        {metrics.total_phase_changes:8d}")
        if metrics.emergency_count > 0:
            print(f"    Emergency Events:     {metrics.emergency_count:8d}")
            print(f"    Avg Preemption Time:  {metrics.avg_emergency_preemption_duration:8.2f}s")
