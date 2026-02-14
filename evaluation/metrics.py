"""
Comprehensive metrics collection for traffic control evaluation.
"""

import numpy as np
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class PerformanceMetrics:
    """Complete performance metrics for a simulation run"""
    controller_name: str
    duration: float
    
    # Efficiency metrics
    avg_waiting_time: float = 0.0
    total_waiting_time: float = 0.0
    avg_queue_length: float = 0.0
    max_queue_length: float = 0.0
    avg_stopped_vehicles: float = 0.0
    
    # Throughput metrics
    total_vehicles_served: int = 0
    avg_vehicles_in_system: float = 0.0
    throughput_rate: float = 0.0  # vehicles/second
    
    # Signal metrics
    total_phase_changes: int = 0
    avg_cycle_length: float = 0.0
    green_time_utilization: float = 0.0
    
    # Emergency metrics (if applicable)
    emergency_count: int = 0
    avg_emergency_response_time: float = 0.0
    avg_emergency_preemption_duration: float = 0.0
    
    # Per-approach metrics
    approach_metrics: Dict[str, Dict] = field(default_factory=dict)
    
    # Time series data
    time_series: Dict[str, List] = field(default_factory=dict)


class MetricsCollector:
    """Collects and computes traffic control performance metrics"""
    
    def __init__(self, controller_name: str):
        self.controller_name = controller_name
        
        # Time series storage
        self.time = []
        self.total_waiting_time = []
        self.total_stopped = []
        self.total_vehicles = []
        self.queue_lengths = {'N': [], 'S': [], 'E': [], 'W': []}
        self.vehicle_counts = {'N': [], 'S': [], 'E': [], 'W': []}
        
        # Event tracking
        self.phase_changes = 0
        self.last_phase_state = None
        self.phase_change_times = []
        
        # Emergency tracking
        self.emergency_events = []
        self.emergency_start_times = {}
        self.emergency_end_times = {}
        
        # Vehicle tracking
        self.vehicles_entered = set()
        self.vehicles_exited = set()
    
    def update(self, intersection_state, signal_state: str, current_time: float,
               controller_status: dict = None):
        """Update metrics with current state"""
        
        # Time series
        self.time.append(current_time)
        
        # Waiting time (sum of all vehicles * their waiting time)
        total_wait = sum(
            m['avg_waiting_time'] * m['total_vehicles']
            for m in intersection_state.approach_metrics.values()
        )
        self.total_waiting_time.append(total_wait)
        
        # Stopped vehicles
        self.total_stopped.append(intersection_state.total_stopped)
        
        # Total vehicles
        self.total_vehicles.append(intersection_state.total_vehicles)
        
        # Per-approach metrics
        for approach in ['N', 'S', 'E', 'W']:
            metrics = intersection_state.approach_metrics[approach]
            self.queue_lengths[approach].append(metrics['total_queue_length'])
            self.vehicle_counts[approach].append(metrics['total_vehicles'])
        
        # Track phase changes
        if self.last_phase_state != signal_state:
            self.phase_changes += 1
            self.phase_change_times.append(current_time)
            self.last_phase_state = signal_state
        
        # Track emergency events
        if controller_status and controller_status.get('mode') == 'EMERGENCY':
            if not hasattr(self, 'emergency_active') or not self.emergency_active:
                self.emergency_active = True
                self.emergency_events.append({
                    'start_time': current_time,
                    'approach': controller_status.get('emergency_approach')
                })
        elif hasattr(self, 'emergency_active') and self.emergency_active:
            self.emergency_active = False
            if self.emergency_events:
                self.emergency_events[-1]['end_time'] = current_time
    
    def finalize(self, duration: float) -> PerformanceMetrics:
        """Compute final metrics"""
        
        # Basic statistics
        avg_waiting = np.mean(self.total_waiting_time) if self.total_waiting_time else 0.0
        total_wait = np.sum(self.total_waiting_time) if self.total_waiting_time else 0.0
        
        avg_stopped = np.mean(self.total_stopped) if self.total_stopped else 0.0
        avg_vehicles = np.mean(self.total_vehicles) if self.total_vehicles else 0.0
        
        # Queue metrics
        all_queues = []
        for approach_queues in self.queue_lengths.values():
            all_queues.extend(approach_queues)
        
        avg_queue = np.mean(all_queues) if all_queues else 0.0
        max_queue = np.max(all_queues) if all_queues else 0.0
        
        # Throughput (simplified - would need actual vehicle tracking)
        total_vehicles_served = len(self.vehicles_exited)
        throughput = total_vehicles_served / duration if duration > 0 else 0.0
        
        # Cycle length
        if len(self.phase_change_times) > 1:
            cycle_lengths = []
            for i in range(2, len(self.phase_change_times), 2):
                cycle_length = self.phase_change_times[i] - self.phase_change_times[i-2]
                cycle_lengths.append(cycle_length)
            avg_cycle = np.mean(cycle_lengths) if cycle_lengths else 0.0
        else:
            avg_cycle = 0.0
        
        # Emergency metrics
        emergency_count = len(self.emergency_events)
        emergency_response_times = []
        emergency_durations = []
        
        for event in self.emergency_events:
            if 'end_time' in event:
                duration = event['end_time'] - event['start_time']
                emergency_durations.append(duration)
        
        avg_emergency_response = np.mean(emergency_response_times) if emergency_response_times else 0.0
        avg_emergency_duration = np.mean(emergency_durations) if emergency_durations else 0.0
        
        # Per-approach summary
        approach_summary = {}
        for approach in ['N', 'S', 'E', 'W']:
            approach_summary[approach] = {
                'avg_queue': np.mean(self.queue_lengths[approach]),
                'max_queue': np.max(self.queue_lengths[approach]) if self.queue_lengths[approach] else 0.0,
                'avg_vehicles': np.mean(self.vehicle_counts[approach])
            }
        
        # Create metrics object
        metrics = PerformanceMetrics(
            controller_name=self.controller_name,
            duration=duration,
            avg_waiting_time=avg_waiting,
            total_waiting_time=total_wait,
            avg_queue_length=avg_queue,
            max_queue_length=max_queue,
            avg_stopped_vehicles=avg_stopped,
            total_vehicles_served=total_vehicles_served,
            avg_vehicles_in_system=avg_vehicles,
            throughput_rate=throughput,
            total_phase_changes=self.phase_changes,
            avg_cycle_length=avg_cycle,
            emergency_count=emergency_count,
            avg_emergency_response_time=avg_emergency_response,
            avg_emergency_preemption_duration=avg_emergency_duration,
            approach_metrics=approach_summary,
            time_series={
                'time': self.time,
                'waiting_time': self.total_waiting_time,
                'stopped': self.total_stopped,
                'vehicles': self.total_vehicles,
                'queue_N': self.queue_lengths['N'],
                'queue_S': self.queue_lengths['S'],
                'queue_E': self.queue_lengths['E'],
                'queue_W': self.queue_lengths['W']
            }
        )
        
        return metrics
