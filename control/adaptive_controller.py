"""
Rule-based adaptive traffic signal controller.
Uses Webster's formula and traffic state to optimize green times.
"""

import numpy as np
from control.signal_phases import SignalPhaseController, PhaseType
from control.safety_validator import SafetyValidator


class AdaptiveController:
    """
    Adaptive controller using Webster's formula.
    Adjusts green times based on traffic demand.
    """
    
    def __init__(self,
                 min_green: float = 10.0,
                 max_green: float = 60.0,
                 saturation_flow: float = 0.5):  # vehicles/second/lane
        """
        Initialize adaptive controller
        
        Args:
            min_green: Minimum green time
            max_green: Maximum green time
            saturation_flow: Saturation flow rate (vehicles/second/lane)
        """
        self.phase_controller = SignalPhaseController()
        self.safety_validator = SafetyValidator()
        
        self.min_green = min_green
        self.max_green = max_green
        self.saturation_flow = saturation_flow
        
        self.current_phase = PhaseType.NS_THROUGH
        self.phase_start_time = 0.0
        self.planned_green_time = min_green
        
        # Transition tracking
        self.in_transition = False
        self.transition_stage = 0
        self.transition_target_phase = None
        
        # Starvation prevention
        self.phase_wait_times = {
            PhaseType.NS_THROUGH: 0.0,
            PhaseType.EW_THROUGH: 0.0
        }
        self.max_wait_before_override = 90.0  # seconds
        
        print(f"✓ Adaptive controller initialized")
    
    def update(self, intersection_state, current_time: float) -> str:
        """
        Update signal with adaptive logic
        
        Args:
            intersection_state: Current IntersectionState
            current_time: Simulation time
            
        Returns:
            SUMO signal state string
        """
        phase_elapsed = current_time - self.phase_start_time
        
        # Check for phase transition
        if not self.in_transition and phase_elapsed >= self.planned_green_time:
            # Decide next phase
            next_phase = self._select_next_phase(intersection_state)
            
            # Calculate green time for next phase
            next_green_time = self._calculate_green_time(intersection_state, next_phase)
            
            # Start transition
            self.in_transition = True
            self.transition_stage = 1
            self.transition_target_phase = next_phase
            self.planned_green_time = next_green_time
            
            # Validate
            is_safe, reason = self.safety_validator.validate_transition(
                self.current_phase, next_phase, current_time, "Adaptive"
            )
            
            if not is_safe:
                print(f"⚠ Transition blocked: {reason}")
                self.in_transition = False
                self.planned_green_time = phase_elapsed + 5.0
        
        # Update wait times for starvation prevention
        self._update_wait_times(intersection_state, phase_elapsed)
        
        # Handle transitions
        if self.in_transition:
            return self._handle_transition(current_time)
        
        # Return current phase
        phase = self.phase_controller.get_phase(self.current_phase)
        return phase.sumo_state_green
    
    def _calculate_green_time(self, intersection_state, phase_type: PhaseType) -> float:
        """
        Calculate optimal green time using Webster's formula
        
        Webster's formula: g = (C - L) * (y / Y)
        Where:
        - C = cycle length
        - L = lost time
        - y = flow for this phase
        - Y = total critical flow
        """
        phase = self.phase_controller.get_phase(phase_type)
        approaches = phase.green_approaches
        
        # Get demand for this phase
        total_queue = 0.0
        total_vehicles = 0
        
        for approach in approaches:
            metrics = intersection_state.approach_metrics.get(approach, {})
            total_queue += metrics.get('total_queue_length', 0.0)
            total_vehicles += metrics.get('total_vehicles', 0)
        
        # Simple proportional allocation
        # More queue/vehicles = longer green
        if total_vehicles == 0:
            return self.min_green
        
        # Estimate time needed to clear queue
        # Assume 7m spacing and saturation flow rate
        vehicles_in_queue = total_queue / 7.0
        clear_time = vehicles_in_queue / (self.saturation_flow * len(approaches) * 3)  # 3 lanes per approach
        
        # Add buffer time for safety
        green_time = clear_time * 1.5
        
        # Apply bounds
        green_time = max(self.min_green, min(self.max_green, green_time))
        
        return green_time
    
    def _select_next_phase(self, intersection_state) -> PhaseType:
        """
        Select next phase based on demand and fairness
        """
        # Simple two-phase cycle with starvation check
        if self.current_phase == PhaseType.NS_THROUGH:
            candidate = PhaseType.EW_THROUGH
        else:
            candidate = PhaseType.NS_THROUGH
        
        # Check for starvation override
        for phase_type, wait_time in self.phase_wait_times.items():
            if wait_time > self.max_wait_before_override and phase_type != self.current_phase:
                print(f"⚠ Starvation override: {phase_type} waited {wait_time:.1f}s")
                return phase_type
        
        return candidate
    
    def _update_wait_times(self, intersection_state, phase_elapsed: float):
        """Track how long each phase has been waiting"""
        # Current phase is being served, reset its wait time
        self.phase_wait_times[self.current_phase] = 0.0
        
        # Other phases accumulate wait time
        for phase_type in self.phase_wait_times.keys():
            if phase_type != self.current_phase:
                self.phase_wait_times[phase_type] += 0.1  # Assuming 0.1s update interval
    
    def _handle_transition(self, current_time: float) -> str:
        """Handle yellow and all-red transitions"""
        current_phase_config = self.phase_controller.get_phase(self.current_phase)
        
        if self.transition_stage == 1:
            # Yellow
            if not hasattr(self, 'yellow_start_time'):
                self.yellow_start_time = current_time
            
            if current_time - self.yellow_start_time >= current_phase_config.yellow_duration:
                self.transition_stage = 2
                self.all_red_start_time = current_time
                del self.yellow_start_time
            
            return current_phase_config.sumo_state_yellow
        
        elif self.transition_stage == 2:
            # All-red
            if current_time - self.all_red_start_time >= current_phase_config.all_red_duration:
                # Complete transition
                self.current_phase = self.transition_target_phase
                self.phase_start_time = current_time
                self.in_transition = False
                self.transition_stage = 0
                
                self.safety_validator.record_transition(current_time)
                del self.all_red_start_time
                
                new_phase = self.phase_controller.get_phase(self.current_phase)
                return new_phase.sumo_state_green
            
            return current_phase_config.sumo_state_red
        
        return current_phase_config.sumo_state_green
    
    def reset(self):
        """Reset controller"""
        self.current_phase = PhaseType.NS_THROUGH
        self.phase_start_time = 0.0
        self.planned_green_time = self.min_green
        self.in_transition = False
        self.phase_wait_times = {pt: 0.0 for pt in self.phase_wait_times.keys()}
