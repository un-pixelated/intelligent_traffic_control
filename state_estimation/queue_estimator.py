"""
Advanced queue length estimation with spatial analysis.
Uses vehicle positions to estimate queue extent and occupancy.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class QueueSegment:
    """Segment of queue"""
    start_distance: float  # Distance from stop line (start of segment)
    end_distance: float    # Distance from stop line (end of segment)
    vehicle_count: int
    density: float  # vehicles/meter in this segment


class QueueEstimator:
    """
    Estimates queue length and structure using spatial binning.
    More sophisticated than simple "furthest stopped vehicle" approach.
    """
    
    def __init__(self, 
                 bin_size: float = 5.0,
                 max_distance: float = 100.0,
                 speed_threshold: float = 0.5):
        """
        Initialize queue estimator
        
        Args:
            bin_size: Size of spatial bins in meters
            max_distance: Maximum distance to consider
            speed_threshold: Speed below which vehicle is considered stopped
        """
        self.bin_size = bin_size
        self.max_distance = max_distance
        self.speed_threshold = speed_threshold
        
        # Create bins
        self.num_bins = int(max_distance / bin_size)
        self.bin_edges = np.linspace(0, max_distance, self.num_bins + 1)
    
    def estimate_queue(self, 
                      vehicle_distances: List[float],
                      vehicle_speeds: List[float]) -> Tuple[float, List[QueueSegment]]:
        """
        Estimate queue length and structure
        
        Args:
            vehicle_distances: List of distances from stop line
            vehicle_speeds: List of vehicle speeds
            
        Returns:
            (queue_length, queue_segments)
        """
        if not vehicle_distances:
            return 0.0, []
        
        # Filter for stopped/slow vehicles
        stopped_distances = [
            d for d, s in zip(vehicle_distances, vehicle_speeds)
            if s < self.speed_threshold and 0 <= d <= self.max_distance
        ]
        
        if not stopped_distances:
            return 0.0, []
        
        # Bin vehicles by distance
        occupancy, _ = np.histogram(stopped_distances, bins=self.bin_edges)
        
        # Find contiguous occupied regions (queue segments)
        segments = []
        in_queue = False
        segment_start_idx = 0
        
        for i, count in enumerate(occupancy):
            if count > 0 and not in_queue:
                # Start of queue segment
                in_queue = True
                segment_start_idx = i
            elif count == 0 and in_queue:
                # End of queue segment
                in_queue = False
                segments.append(self._create_segment(
                    segment_start_idx, i, occupancy
                ))
            elif i == len(occupancy) - 1 and in_queue:
                # Queue extends to end
                segments.append(self._create_segment(
                    segment_start_idx, i + 1, occupancy
                ))
        
        # Queue length = extent of first (closest) queue segment
        if segments:
            queue_length = segments[0].end_distance
        else:
            queue_length = 0.0
        
        return queue_length, segments
    
    def _create_segment(self, start_idx: int, end_idx: int, 
                       occupancy: np.ndarray) -> QueueSegment:
        """Create queue segment from bin indices"""
        start_dist = self.bin_edges[start_idx]
        end_dist = self.bin_edges[end_idx]
        vehicle_count = int(np.sum(occupancy[start_idx:end_idx]))
        
        segment_length = end_dist - start_dist
        density = vehicle_count / segment_length if segment_length > 0 else 0.0
        
        return QueueSegment(
            start_distance=start_dist,
            end_distance=end_dist,
            vehicle_count=vehicle_count,
            density=density
        )
    
    def estimate_queue_delay(self, queue_length: float, 
                           discharge_rate: float = 0.5) -> float:
        """
        Estimate time to clear queue
        
        Args:
            queue_length: Length of queue in meters
            discharge_rate: Vehicles per second that can discharge
            
        Returns:
            Estimated delay in seconds
        """
        # Assume 7m per vehicle spacing
        vehicles_in_queue = queue_length / 7.0
        
        # Time to clear = vehicles / discharge rate
        clear_time = vehicles_in_queue / discharge_rate if discharge_rate > 0 else 0.0
        
        return clear_time
