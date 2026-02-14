"""
Traffic scenario generator for comprehensive testing.
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class EmergencyEvent:
    """Emergency vehicle spawn event"""
    spawn_time: float
    route: str
    vehicle_type: str


@dataclass
class TrafficScenario:
    """Complete traffic scenario definition"""
    name: str
    description: str
    duration: float  # seconds
    flow_multiplier: float  # Multiply base flows
    emergency_events: List[EmergencyEvent]
    
    # Flow imbalance (optional)
    directional_bias: dict = None  # e.g., {'N': 1.5, 'S': 0.8, 'E': 1.0, 'W': 1.0}


class ScenarioGenerator:
    """Generates standard test scenarios"""
    
    @staticmethod
    def get_baseline_scenario() -> TrafficScenario:
        """Normal balanced traffic, no emergencies"""
        return TrafficScenario(
            name="Baseline",
            description="Normal balanced traffic, no emergencies",
            duration=300.0,
            flow_multiplier=1.0,
            emergency_events=[]
        )
    
    @staticmethod
    def get_single_emergency_scenario() -> TrafficScenario:
        """Normal traffic with one emergency vehicle"""
        return TrafficScenario(
            name="Single Emergency",
            description="Normal traffic with ambulance at t=150s",
            duration=300.0,
            flow_multiplier=1.0,
            emergency_events=[
                EmergencyEvent(
                    spawn_time=150.0,
                    route="N_S",
                    vehicle_type="ambulance"
                )
            ]
        )
    
    @staticmethod
    def get_multiple_emergency_scenario() -> TrafficScenario:
        """Multiple emergency vehicles from different directions"""
        return TrafficScenario(
            name="Multiple Emergencies",
            description="Three emergency vehicles at different times",
            duration=400.0,
            flow_multiplier=1.0,
            emergency_events=[
                EmergencyEvent(spawn_time=100.0, route="N_S", vehicle_type="ambulance"),
                EmergencyEvent(spawn_time=200.0, route="E_W", vehicle_type="fire_truck"),
                EmergencyEvent(spawn_time=300.0, route="S_N", vehicle_type="ambulance")
            ]
        )
    
    @staticmethod
    def get_peak_traffic_scenario() -> TrafficScenario:
        """Heavy traffic with emergency"""
        return TrafficScenario(
            name="Peak Traffic",
            description="Heavy traffic (1.5x) with emergency at t=180s",
            duration=360.0,
            flow_multiplier=1.5,
            emergency_events=[
                EmergencyEvent(spawn_time=180.0, route="N_S", vehicle_type="ambulance")
            ]
        )
    
    @staticmethod
    def get_imbalanced_scenario() -> TrafficScenario:
        """Imbalanced traffic (heavy N-S, light E-W)"""
        return TrafficScenario(
            name="Imbalanced Traffic",
            description="Heavy N-S (1.5x), Light E-W (0.5x)",
            duration=300.0,
            flow_multiplier=1.0,
            emergency_events=[],
            directional_bias={'N': 1.5, 'S': 1.5, 'E': 0.5, 'W': 0.5}
        )
    
    @staticmethod
    def get_all_scenarios() -> List[TrafficScenario]:
        """Get all test scenarios"""
        return [
            ScenarioGenerator.get_baseline_scenario(),
            ScenarioGenerator.get_single_emergency_scenario(),
            ScenarioGenerator.get_multiple_emergency_scenario(),
            ScenarioGenerator.get_peak_traffic_scenario(),
            ScenarioGenerator.get_imbalanced_scenario()
        ]
