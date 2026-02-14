"""
Estimates vehicle distance to intersection using Kalman filtering.
Smooths noisy measurements and predicts positions.
"""

import numpy as np
from filterpy.kalman import KalmanFilter
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class VehicleState:
    """Estimated vehicle state"""
    position: Tuple[float, float]  # (x, y)
    velocity: Tuple[float, float]  # (vx, vy)
    distance_to_intersection: float
    lane_id: str
    confidence: float


class KalmanDistanceEstimator:
    """
    Kalman filter-based distance estimator.
    Tracks vehicle position and velocity for smooth distance estimation.
    """
    
    def __init__(self, dt: float = 0.1):
        """
        Initialize estimator
        
        Args:
            dt: Time step in seconds
        """
        self.dt = dt
        self.filters: Dict[int, KalmanFilter] = {}  # track_id -> KalmanFilter
    
    def update(self, track_id: int, 
              position: Tuple[float, float],
              measurement_noise: float = 2.0) -> Tuple[float, float, float, float]:
        """
        Update state estimate for a tracked vehicle
        
        Args:
            track_id: Unique track identifier
            position: Measured position (x, y)
            measurement_noise: Measurement uncertainty in meters
            
        Returns:
            (x, y, vx, vy): Estimated position and velocity
        """
        if track_id not in self.filters:
            # Initialize new Kalman filter for this track
            self.filters[track_id] = self._create_filter(position)
        
        kf = self.filters[track_id]
        
        # Predict
        kf.predict()
        
        # Update with measurement
        z = np.array([position[0], position[1]])
        kf.update(z)
        
        # Extract state
        x, vx, y, vy = kf.x.flatten()
        
        return (x, y, vx, vy)
    
    def _create_filter(self, initial_position: Tuple[float, float]) -> KalmanFilter:
        """
        Create Kalman filter for constant velocity model
        
        State: [x, vx, y, vy]
        Measurement: [x, y]
        """
        kf = KalmanFilter(dim_x=4, dim_z=2)
        
        # State transition matrix (constant velocity)
        dt = self.dt
        kf.F = np.array([
            [1, dt, 0,  0],   # x = x + vx*dt
            [0,  1, 0,  0],   # vx = vx
            [0,  0, 1, dt],   # y = y + vy*dt
            [0,  0, 0,  1]    # vy = vy
        ])
        
        # Measurement matrix (observe position only)
        kf.H = np.array([
            [1, 0, 0, 0],
            [0, 0, 1, 0]
        ])
        
        # Initial state
        kf.x = np.array([initial_position[0], 0, initial_position[1], 0])
        
        # Process noise (model uncertainty)
        q = 0.5  # Process noise magnitude
        kf.Q = np.array([
            [dt**4/4, dt**3/2, 0, 0],
            [dt**3/2, dt**2,   0, 0],
            [0, 0, dt**4/4, dt**3/2],
            [0, 0, dt**3/2, dt**2]
        ]) * q
        
        # Measurement noise
        r = 2.0  # 2 meter measurement uncertainty
        kf.R = np.eye(2) * r**2
        
        # Initial covariance
        kf.P = np.eye(4) * 10.0
        
        return kf
    
    def remove_track(self, track_id: int):
        """Remove filter for lost track"""
        if track_id in self.filters:
            del self.filters[track_id]
    
    def reset(self):
        """Reset all filters"""
        self.filters.clear()
