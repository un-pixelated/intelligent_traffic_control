"""
Perception module - Day 1 architecture (frozen interfaces).

Exports:
    - PerceivedVehicle: Frozen output dataclass
    - PerceptionAdapter: Abstract base for all perception implementations
    - SumoPerceptionAdapter: Ground truth perception
    - VisionPerceptionAdapter: ML vision (Day 5)
    - LaneMapper: Lane geometry and assignment
    - EmergencyVehicleDetector: Unified emergency detection
"""

# Frozen interfaces (Days 1-5)
from perception.types import PerceivedVehicle
from perception.base import PerceptionAdapter

# Perception adapters
from perception.sumo_adapter import SumoPerceptionAdapter
from perception.vision_adapter import VisionPerceptionAdapter

# Supporting modules
from perception.lane_mapper import LaneMapper
from perception.emergency_detection import EmergencyVehicleDetector

# ML vision components (for Day 5 implementation)
from perception.perception_pipeline import PerceptionPipeline
from perception.detector import VehicleDetector
from perception.tracker import ByteTracker
from perception.distance_estimator import KalmanDistanceEstimator

__all__ = [
    # Core interfaces
    'PerceivedVehicle',
    'PerceptionAdapter',
    
    # Adapters
    'SumoPerceptionAdapter',
    'VisionPerceptionAdapter',
    
    # Supporting
    'LaneMapper',
    'EmergencyVehicleDetector',
    
    # ML components
    'PerceptionPipeline',
    'VehicleDetector',
    'ByteTracker',
    'KalmanDistanceEstimator',
]
