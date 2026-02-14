"""
Fixed-time traffic signal controller.
Simple baseline using predetermined cycle times.
"""

from control.signal_phases import SignalPhaseController, PhaseType
from control.safety_validator import SafetyValidator


class FixedTimeController:
    """
    Fixed-time signal controller with predetermined cycle.
    Baseline for comparison with adaptive methods.
    """
    
    def __init__(self, 
                 ns_green_time: float = 30.0,
                 ew_green_time: float = 30.0):
        """
        Initialize fixed-time controller
        
        Args:
            ns_green_time: Green time for North-South phase
            ew_green_time: Green time for East-West phase
        """
        self.phase_controller = SignalPhaseController()
        self.safety_validator = SafetyValidator()
        
        self.ns_green_time = ns_green_time
        self.ew_green_time = ew_green_time
        
        self.current_phase = PhaseType.NS_THROUGH
        self.phase_start_time = 0.0
        self.next_transition_time = ns_green_time
        
        # State tracking
        self.in_transition = False
        self.transition_stage = 0  # 0=green, 1=yellow, 2=all_red
        self.transition_target_phase = None
        
        print(f"✓ Fixed-time controller initialized (NS:{ns_green_time}s, EW:{ew_green_time}s)")
    
    def update(self, intersection_state, current_time: float) -> str:
        """
        Update signal state (fixed-time logic)
        
        Args:
            intersection_state: Current traffic state (ignored for fixed-time)
            current_time: Current simulation time
            
        Returns:
            SUMO signal state string
        """
        # Check if it's time to transition
        if not self.in_transition and current_time >= self.next_transition_time:
            # Start transition
            self.in_transition = True
            self.transition_stage = 1  # Start with yellow
            self.transition_target_phase = self._get_next_phase()
            
            # Validate transition
            is_safe, reason = self.safety_validator.validate_transition(
                self.current_phase,
                self.transition_target_phase,
                current_time,
                "Fixed-time cycle"
            )
            
            if not is_safe:
                print(f"⚠ Transition blocked: {reason}")
                self.in_transition = False
                self.next_transition_time = current_time + 5.0  # Retry later
        
        # Handle transition stages
        if self.in_transition:
            return self._handle_transition(current_time)
        
        # Return current phase state
        phase = self.phase_controller.get_phase(self.current_phase)
        return phase.sumo_state_green
    
    def _handle_transition(self, current_time: float) -> str:
        """Handle yellow and all-red transition phases"""
        current_phase_config = self.phase_controller.get_phase(self.current_phase)
        
        if self.transition_stage == 1:
            # Yellow phase
            if not hasattr(self, 'yellow_start_time'):
                self.yellow_start_time = current_time
            
            yellow_elapsed = current_time - self.yellow_start_time
            
            if yellow_elapsed >= current_phase_config.yellow_duration:
                # Move to all-red
                self.transition_stage = 2
                self.all_red_start_time = current_time
                del self.yellow_start_time
            
            return current_phase_config.sumo_state_yellow
        
        elif self.transition_stage == 2:
            # All-red phase
            all_red_elapsed = current_time - self.all_red_start_time
            
            if all_red_elapsed >= current_phase_config.all_red_duration:
                # Transition complete - switch to new phase
                self.current_phase = self.transition_target_phase
                self.phase_start_time = current_time
                self.in_transition = False
                self.transition_stage = 0
                
                # Schedule next transition
                if self.current_phase == PhaseType.NS_THROUGH:
                    self.next_transition_time = current_time + self.ns_green_time
                else:
                    self.next_transition_time = current_time + self.ew_green_time
                
                # Record transition
                self.safety_validator.record_transition(current_time)
                
                del self.all_red_start_time
                
                # Return new phase green
                new_phase_config = self.phase_controller.get_phase(self.current_phase)
                return new_phase_config.sumo_state_green
            
            return current_phase_config.sumo_state_red
        
        # Shouldn't reach here
        return current_phase_config.sumo_state_green
    
    def _get_next_phase(self) -> PhaseType:
        """Get next phase in fixed cycle"""
        if self.current_phase == PhaseType.NS_THROUGH:
            return PhaseType.EW_THROUGH
        else:
            return PhaseType.NS_THROUGH
    
    def reset(self):
        """Reset controller state"""
        self.current_phase = PhaseType.NS_THROUGH
        self.phase_start_time = 0.0
        self.next_transition_time = self.ns_green_time
        self.in_transition = False
        self.transition_stage = 0
