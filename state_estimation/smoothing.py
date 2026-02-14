"""
Smoothing filters for noisy traffic measurements.
Uses exponential moving average (EMA) for real-time smoothing.
"""

import numpy as np
from typing import Dict, Optional
from collections import defaultdict


class ExponentialMovingAverage:
    """
    Exponential Moving Average filter.
    Smooths noisy measurements while being responsive to changes.
    """
    
    def __init__(self, alpha: float = 0.3):
        """
        Initialize EMA filter
        
        Args:
            alpha: Smoothing factor (0-1)
                  0 = no update (ignore new data)
                  1 = no smoothing (use raw data)
                  0.3 = good balance for traffic
        """
        self.alpha = alpha
        self.state: Dict[str, float] = {}
    
    def update(self, key: str, value: float) -> float:
        """
        Update EMA for a key
        
        Args:
            key: Identifier (e.g., lane_id)
            value: New measurement
            
        Returns:
            Smoothed value
        """
        if key not in self.state:
            # Initialize with first measurement
            self.state[key] = value
        else:
            # EMA update: S_t = α * x_t + (1-α) * S_{t-1}
            self.state[key] = self.alpha * value + (1 - self.alpha) * self.state[key]
        
        return self.state[key]
    
    def get(self, key: str, default: float = 0.0) -> float:
        """Get current smoothed value"""
        return self.state.get(key, default)
    
    def reset(self, key: Optional[str] = None):
        """Reset state for key or all keys"""
        if key:
            self.state.pop(key, None)
        else:
            self.state.clear()


class MultiVariableEMA:
    """
    EMA filter for multiple variables with different smoothing factors.
    Useful for smoothing different traffic metrics simultaneously.
    """
    
    def __init__(self, alphas: Dict[str, float]):
        """
        Initialize multi-variable EMA
        
        Args:
            alphas: Dictionary of variable_name -> smoothing_factor
        """
        self.filters = {
            var: ExponentialMovingAverage(alpha)
            for var, alpha in alphas.items()
        }
    
    def update(self, key: str, values: Dict[str, float]) -> Dict[str, float]:
        """
        Update all variables for a key
        
        Args:
            key: Identifier (e.g., lane_id)
            values: Dictionary of variable_name -> measurement
            
        Returns:
            Dictionary of variable_name -> smoothed_value
        """
        smoothed = {}
        
        for var, value in values.items():
            if var in self.filters:
                smoothed[var] = self.filters[var].update(f"{key}_{var}", value)
            else:
                # No smoothing for unknown variables
                smoothed[var] = value
        
        return smoothed
    
    def get(self, key: str, var: str, default: float = 0.0) -> float:
        """Get smoothed value for specific variable"""
        if var in self.filters:
            return self.filters[var].get(f"{key}_{var}", default)
        return default


class AdaptiveEMA:
    """
    EMA with adaptive smoothing factor based on measurement variance.
    More smoothing when measurements are noisy, less when stable.
    """
    
    def __init__(self, 
                 alpha_min: float = 0.1,
                 alpha_max: float = 0.5,
                 variance_window: int = 10):
        """
        Initialize adaptive EMA
        
        Args:
            alpha_min: Minimum smoothing factor (high smoothing)
            alpha_max: Maximum smoothing factor (low smoothing)
            variance_window: Window size for variance calculation
        """
        self.alpha_min = alpha_min
        self.alpha_max = alpha_max
        self.variance_window = variance_window
        
        self.state: Dict[str, float] = {}
        self.history: Dict[str, list] = defaultdict(list)
    
    def update(self, key: str, value: float) -> float:
        """Update with adaptive smoothing"""
        # Add to history
        self.history[key].append(value)
        if len(self.history[key]) > self.variance_window:
            self.history[key].pop(0)
        
        # Calculate adaptive alpha
        if len(self.history[key]) >= 3:
            variance = np.var(self.history[key])
            # High variance -> low alpha (more smoothing)
            # Low variance -> high alpha (less smoothing)
            alpha = self.alpha_max - (variance / (variance + 1)) * (self.alpha_max - self.alpha_min)
            alpha = np.clip(alpha, self.alpha_min, self.alpha_max)
        else:
            alpha = self.alpha_max
        
        # Update EMA
        if key not in self.state:
            self.state[key] = value
        else:
            self.state[key] = alpha * value + (1 - alpha) * self.state[key]
        
        return self.state[key]
    
    def get(self, key: str, default: float = 0.0) -> float:
        """Get current smoothed value"""
        return self.state.get(key, default)
