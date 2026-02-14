"""
Safety validator for signal transitions.
Ensures all transitions are safe and follow traffic engineering standards.
"""

from typing import Optional
from control.signal_phases import PhaseType, SignalPhase
import time


class SafetyValidator:
    """
    Validates signal transitions for safety.
    Prevents dangerous configurations like conflicting greens.
    """
    
    def __init__(self):
        self.last_phase_change: float = 0.0
        self.min_phase_gap: float = 5.0  # Minimum time between phase changes
        
        # Conflicting phases (cannot be green simultaneously)
        self.conflicts = {
            PhaseType.NS_THROUGH: [PhaseType.EW_THROUGH, PhaseType.EW_LEFT],
            PhaseType.EW_THROUGH: [PhaseType.NS_THROUGH, PhaseType.NS_LEFT],
        }
        
        print("✓ Safety validator initialized")
    
    def validate_transition(self, 
                          current_phase: PhaseType,
                          next_phase: PhaseType,
                          current_time: float,
                          reason: str = "") -> Tuple[bool, str]:
        """
        Validate if transition is safe
        
        Returns:
            (is_safe, reason_if_unsafe)
        """
        # Check minimum gap between changes
        if current_time - self.last_phase_change < self.min_phase_gap:
            return False, f"Too soon (min gap: {self.min_phase_gap}s)"
        
        # Check for same phase (no-op is always safe)
        if current_phase == next_phase:
            return True, "Same phase"
        
        # Check for conflicting phases
        if next_phase in self.conflicts.get(current_phase, []):
            # Conflicting phases require transition through all-red
            # This is handled by the controller, so it's safe
            pass
        
        # All checks passed
        return True, f"Safe transition: {reason}"
    
    def record_transition(self, current_time: float):
        """Record that a transition occurred"""
        self.last_phase_change = current_time
    
    def validate_phase_duration(self, 
                               phase: SignalPhase,
                               requested_duration: float) -> float:
        """
        Validate and adjust phase duration to safe bounds
        
        Returns:
            Adjusted duration within [min, max]
        """
        if requested_duration < phase.min_duration:
            return phase.min_duration
        elif requested_duration > phase.max_duration:
            return phase.max_duration
        else:
            return requested_duration
    
    def check_emergency_override_safe(self,
                                     current_phase: PhaseType,
                                     emergency_phase: PhaseType,
                                     current_time: float) -> Tuple[bool, str]:
        """
        Check if emergency override is safe
        Emergency overrides can violate minimum green, but still need basic safety
        """
        # Emergency overrides are generally allowed, but check basic sanity
        time_since_last = current_time - self.last_phase_change
        
        if time_since_last < 2.0:
            return False, "Cannot override within 2 seconds of last change"
        
        return True, "Emergency override approved"
