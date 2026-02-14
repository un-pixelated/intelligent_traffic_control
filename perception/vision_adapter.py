"""
ML-based vision perception adapter (Day 5+).

Uses camera images + detection/tracking models.
This is a stub - implementation will happen in Day 5.

Author: Architecture Review Day 1
Date: 2026-02-14
"""
from typing import List
from perception.base import PerceptionAdapter
from perception.types import PerceivedVehicle


class VisionPerceptionAdapter(PerceptionAdapter):
    """
    Computer vision-based perception (Day 5 implementation).
    
    Pipeline:
        Camera Image → Detector → Tracker → Lane Mapper → PerceivedVehicles
    
    TODO: Implement in Day 5 using existing perception_pipeline.py logic
    """
    
    def __init__(self, 
                 camera_interface,
                 lane_mapper,
                 model_config: dict):
        """Initialize vision perception adapter."""
        self.camera = camera_interface
        self.lane_mapper = lane_mapper
        self.model_config = model_config
        raise NotImplementedError(
            "VisionPerceptionAdapter not yet implemented - Day 5"
        )
    
    def perceive(self, timestamp: float) -> List[PerceivedVehicle]:
        """Perform ML-based perception."""
        raise NotImplementedError(
            "VisionPerceptionAdapter not yet implemented - Day 5"
        )
    
    def reset(self):
        """Reset vision perception state."""
        raise NotImplementedError(
            "VisionPerceptionAdapter not yet implemented - Day 5"
        )
    
    @property
    def name(self) -> str:
        """Return adapter name."""
        return "ML Vision"
