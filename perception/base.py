"""
Abstract base for perception adapters.

All perception implementations must conform to this interface,
ensuring swappable perception backends without changing downstream code.

Author: Architecture Review Day 1
Date: 2026-02-14
Status: FROZEN - Do not modify without architecture review
"""
from abc import ABC, abstractmethod
from typing import List
from perception.types import PerceivedVehicle


class PerceptionAdapter(ABC):
    """
    Abstract interface for perception subsystems.
    
    Perception adapters convert raw sensor data OR ground truth
    into the standardized PerceivedVehicle format.
    
    Implementations:
        - SumoPerceptionAdapter: Uses SUMO ground truth via TraCI
        - VisionPerceptionAdapter: Uses camera + ML models (Day 5+)
    """
    
    @abstractmethod
    def perceive(self, timestamp: float) -> List[PerceivedVehicle]:
        """
        Perform perception and return detected vehicles.
        
        Args:
            timestamp: Current simulation time (seconds)
            
        Returns:
            List of PerceivedVehicle objects detected at this timestep.
            Empty list if no vehicles detected.
        """
        pass
    
    @abstractmethod
    def reset(self):
        """
        Reset perception state for new simulation episode.
        
        Clears all internal tracking state.
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of perception method."""
        pass
    
    def get_statistics(self) -> dict:
        """Get perception statistics (optional)."""
        return {}
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}(name='{self.name}')"
