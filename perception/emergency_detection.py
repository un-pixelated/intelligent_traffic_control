"""
Emergency vehicle detection logic.

Shared by all perception adapters to ensure consistent emergency
vehicle identification across ground truth and ML vision modes.

Author: Architecture Review Day 1
Date: 2026-02-14
"""
from typing import Set


class EmergencyVehicleDetector:
    """
    Unified emergency vehicle detection.
    
    Handles differences between:
    - Ground truth: Exact vType strings from SUMO
    - Vision: Noisy class names from ML detector
    """
    
    # ========== Ground Truth Emergency Types ==========
    GT_EMERGENCY_TYPES: Set[str] = frozenset([
        'ambulance',
        'fire_truck',
        'police',
        'emergency'
    ])
    
    # ========== Vision Detection Keywords ==========
    VISION_KEYWORDS: Set[str] = frozenset([
        'ambulance',
        'fire truck',
        'firetruck',
        'fire',
        'emergency',
        'emergency vehicle',
        'police',
        'police car',
        'patrol car'
    ])
    
    @staticmethod
    def is_emergency_gt(vtype: str) -> bool:
        """
        Detect emergency vehicle from SUMO vType (exact match).
        
        Args:
            vtype: SUMO vehicle type ID (e.g., "ambulance", "car")
        
        Returns:
            True if vtype is in GT_EMERGENCY_TYPES, False otherwise
        """
        return vtype in EmergencyVehicleDetector.GT_EMERGENCY_TYPES
    
    @staticmethod
    def is_emergency_vision(class_name: str) -> bool:
        """
        Detect emergency vehicle from vision class name (fuzzy match).
        
        Args:
            class_name: ML detector class label (may contain spaces, capitals)
        
        Returns:
            True if any keyword is substring of class_name (case-insensitive)
        """
        class_lower = class_name.lower()
        return any(keyword in class_lower 
                  for keyword in EmergencyVehicleDetector.VISION_KEYWORDS)
