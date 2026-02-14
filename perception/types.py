"""
Perception output types - FROZEN for Days 1-5.

This module defines the standardized output format for all perception
subsystems. The interface must remain stable even as perception 
implementations change (SUMO GT → ML vision).

Author: Architecture Review Day 1
Date: 2026-02-14
Status: FROZEN - Do not modify without architecture review
"""
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass(frozen=True)
class PerceivedVehicle:
    """
    Perceived vehicle information from any perception source.
    
    This dataclass represents the OUTPUT of perception subsystems and serves
    as the boundary between perception and state estimation layers.
    
    Coordinate System:
        - position: World coordinates (meters), intersection-relative
        - velocity: World velocity (m/s), Cartesian components
        - lane_id: Intersection-specific lane identifier (e.g., "N_in_0")
    
    Field Guarantees:
        - track_id: Unique integer within current timestep, stable across frames
        - position: Always valid world coordinates (x, y)
        - lane_id: None if vehicle not in any approach lane
        - distance_to_stop_line: -1.0 if not in a valid lane
        - is_emergency: Conservative detection (false negatives acceptable)
        - confidence: [0.0, 1.0], 1.0 for ground truth
    
    Perception Source Compatibility:
        - Ground Truth (SUMO): All fields populated with perfect accuracy
        - ML Vision: May have noisy positions, confidence < 1.0
        - Future sensors: Must conform to this same interface
    """
    
    # ========== Identity ==========
    track_id: int
    
    # ========== Classification ==========
    class_name: str
    is_emergency: bool
    confidence: float
    
    # ========== Kinematics (World Frame) ==========
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    
    # ========== Lane Assignment (Intersection-Specific) ==========
    lane_id: Optional[str]
    distance_to_stop_line: float
    
    # ========== Optional Fields ==========
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    
    def __post_init__(self):
        """Validate invariants at construction time."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0, 1], got {self.confidence}"
            )
        
        if not isinstance(self.track_id, int):
            raise TypeError(
                f"track_id must be int, got {type(self.track_id).__name__}"
            )
        
        if self.lane_id is None and self.distance_to_stop_line != -1.0:
            raise ValueError(
                "distance_to_stop_line must be -1.0 when lane_id is None, "
                f"got {self.distance_to_stop_line}"
            )
