"""
FINAL COMPREHENSIVE EVALUATION
Compares all controllers across all scenarios.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from control.fixed_time_controller import FixedTimeController
from control.adaptive_controller import AdaptiveController
from control.signal_controller import IntegratedSignalController
from evaluation.evaluator import TrafficControlEvaluator
from evaluation.scenarios import ScenarioGenerator
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def create_controllers():
    """
    Factory function to create fresh controller instances.
    
    Creates new instances for each scenario to ensure clean state.
    This eliminates any risk of state leakage between scenarios.
    
    Returns:
        List of (controller_instance, controller_name) tuples
    """
    return [
        (FixedTimeController(ns_green_time=30, ew_green_time=30), "Fixed-Time"),
        (AdaptiveController(min_green=10, max_green=60), "Adaptive"),
        (IntegratedSignalController(), "Adaptive+Emergency")
    ]


def main():
    print("="*70)
    print(" INTELLIGENT TRAFFIC LIGHT CONTROL SYSTEM")
    print(" FINAL COMPREHENSIVE EVALUATION")
    print("="*70)
    
    # Paths
    config_file = str(project_root / "sumo_networks" / "simple_4way" / "sumo.cfg")
    intersection_config = str(project_root / "config" / "intersection_config.yaml")
    output_dir = project_root / "results" / "final_evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize evaluator
    evaluator = TrafficControlEvaluator(config_file, intersection_config)
    
    # Get test scenarios
    scenarios = [
        ScenarioGenerator.get_baseline_scenario(),
        ScenarioGenerator.get_single_emergency_scenario(),
        ScenarioGenerator.get_peak_traffic_scenario()
    ]
    
    print(f"\nRunning 3 controllers × {len(scenarios)} scenarios")
    print(f"Total experiments: {3 * len(scenarios)}\n")
    
    # Run all experiments
    all_results = {}
    
    for scenario in scenarios:
        all_results[scenario.name] = {}
        
        # Create fresh controller instances for this scenario
        # This ensures clean state - no reliance on reset()
        controllers = create_controllers()
        
        for controller, name in controllers:
            # No reset needed - brand new instance
            metrics = evaluator.evaluate_controller(
                controller, name, scenario, verbose=True
            )
            
            all_results[scenario.name][name] = metrics
    
    # Generate comprehensive comparison
    print(f"\n{'='*70}")
    print("GENERATING COMPARISON PLOTS")
    print(f"{'='*70}\n")
    
    # Create mega comparison plot
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    
    controller_names = ["Fixed-Time", "Adaptive", "Adaptive+Emergency"]
    colors = ['#3498db', '#e74c3c', '#2ecc71']
    
    # Row 1: Baseline scenario
    scenario_name = "Baseline"
    for col, metric_name in enumerate(['avg_waiting_time', 'avg_queue_length', 'avg_stopped_vehicles', 'total_phase_changes']):
        ax = fig.add_subplot(gs[0, col])
        values = [all_results[scenario_name][name].__dict__[metric_name] for name in controller_names]
        ax.bar(controller_names, values, color=colors, alpha=0.7)
        ax.set_title(f"{scenario_name}: {metric_name.replace('_', ' ').title()}")
        ax.grid(True, alpha=0.3, axis='y')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=15, ha='right')
    
    # Row 2: Single Emergency scenario
    scenario_name = "Single Emergency"
    for col, metric_name in enumerate(['avg_waiting_time', 'avg_queue_length', 'avg_stopped_vehicles', 'emergency_count']):
        ax = fig.add_subplot(gs[1, col])
        values = [all_results[scenario_name][name].__dict__[metric_name] for name in controller_names]
        ax.bar(controller_names, values, color=colors, alpha=0.7)
        ax.set_title(f"{scenario_name}: {metric_name.replace('_', ' ').title()}")
        ax.grid(True, alpha=0.3, axis='y')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=15, ha='right')
    
    # Row 3: Peak Traffic scenario
    scenario_name = "Peak Traffic"
    for col, metric_name in enumerate(['avg_waiting_time', 'avg_queue_length', 'avg_stopped_vehicles', 'total_phase_changes']):
        ax = fig.add_subplot(gs[2, col])
        values = [all_results[scenario_name][name].__dict__[metric_name] for name in controller_names]
        ax.bar(controller_names, values, color=colors, alpha=0.7)
        ax.set_title(f"{scenario_name}: {metric_name.replace('_', ' ').title()}")
        ax.grid(True, alpha=0.3, axis='y')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=15, ha='right')
    
    fig.suptitle('Comprehensive Controller Comparison Across Scenarios', fontsize=16, fontweight='bold')
    
    plot_path = output_dir / "comprehensive_comparison.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"✓ Comprehensive plot saved: {plot_path}")
    
    # Generate summary table
    print(f"\n{'='*70}")
    print("PERFORMANCE SUMMARY TABLE")
    print(f"{'='*70}\n")
    
    summary_data = []
    for scenario_name in all_results.keys():
        for controller_name in controller_names:
            metrics = all_results[scenario_name][controller_name]
            summary_data.append({
                'Scenario': scenario_name,
                'Controller': controller_name,
                'Avg Wait (s)': f"{metrics.avg_waiting_time:.2f}",
                'Avg Queue (m)': f"{metrics.avg_queue_length:.2f}",
                'Avg Stopped': f"{metrics.avg_stopped_vehicles:.2f}",
                'Phase Changes': metrics.total_phase_changes,
                'Emergencies': metrics.emergency_count
            })
    
    df = pd.DataFrame(summary_data)
    print(df.to_string(index=False))
    
    # Save to CSV
    csv_path = output_dir / "performance_summary.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n✓ Summary table saved: {csv_path}")
    
    # Calculate improvements
    print(f"\n{'='*70}")
    print("IMPROVEMENT ANALYSIS (vs Fixed-Time Baseline)")
    print(f"{'='*70}\n")
    
    for scenario_name in all_results.keys():
        print(f"\n{scenario_name}:")
        baseline_wait = all_results[scenario_name]["Fixed-Time"].avg_waiting_time
        
        for controller_name in ["Adaptive", "Adaptive+Emergency"]:
            controller_wait = all_results[scenario_name][controller_name].avg_waiting_time
            improvement = ((baseline_wait - controller_wait) / baseline_wait) * 100
            
            print(f"  {controller_name:20s}: {improvement:+6.2f}% waiting time reduction")
    
    print(f"\n{'='*70}")
    print("✓ FINAL EVALUATION COMPLETE!")
    print(f"{'='*70}")
    print(f"\nResults saved to: {output_dir}")
    print(f"  - {plot_path.name}")
    print(f"  - {csv_path.name}")
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()