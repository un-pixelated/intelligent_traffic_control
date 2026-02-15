"""
Main signal controller integrating adaptive control and emergency priority.
Acts as arbiter between normal operation and emergency preemption.

Day 3: Uses clean circuit breaker pattern with emergency controller.
"""

from control.adaptive_controller import AdaptiveController
from control.emergency_priority import EmergencyPriorityController
from control.signal_phases import PhaseType, SignalPhaseController


class IntegratedSignalController:
    """
    Integrated signal controller - Day 3 Production Version.
    
    Combines adaptive control with emergency vehicle priority.
    Emergency controller has absolute priority when active.
    
    Architecture:
        - Normal operation: adaptive_controller runs
        - Emergency detected: emergency_controller overrides
        - Clean handoff: normal controller unaware of override
        
    Circuit Breaker Pattern:
        if emergency_controller.is_active():
            return emergency_signal
        else:
            return normal_controller_signal
    """
    
    def __init__(self):
        """Initialize integrated controller"""
        # Normal adaptive controller
        self.adaptive_controller = AdaptiveController(
            min_green=10.0,
            max_green=60.0,
            saturation_flow=0.5
        )
        
        # Emergency priority controller (Day 3)
        self.emergency_controller = EmergencyPriorityController()
        
        # Phase controller for signal state lookup
        self.phase_controller = SignalPhaseController()
        
        # Mode tracking
        self.in_emergency_mode = False
        
        print("✓ Integrated signal controller initialized")
    
    def update(self, intersection_state, current_time: float) -> str:
        """
        Update signal control with emergency priority.
        
        Args:
            intersection_state: Current traffic state (IntersectionState)
            current_time: Simulation time (seconds)
            
        Returns:
            SUMO signal state string (12 characters)
            
        Logic:
            1. Update emergency controller (state machine)
            2. Check if emergency is active
            3. If active: return emergency phase signal
            4. If not active: return normal controller signal
        """
        # Update emergency controller state machine
        self.emergency_controller.update(intersection_state, current_time)
        
        # Get emergency controller decision
        is_emergency, emergency_phase = self.emergency_controller.get_signal_command()
        
        if is_emergency:
            # EMERGENCY MODE - override normal control
            if not self.in_emergency_mode:
                print(f"⚠️  SWITCHING TO EMERGENCY MODE")
                self.in_emergency_mode = True
            
            # Get emergency phase signal state
            phase_config = self.phase_controller.get_phase(emergency_phase)
            return phase_config.sumo_state_green
        
        else:
            # NORMAL MODE - use adaptive control
            if self.in_emergency_mode:
                print(f"✓  RETURNING TO NORMAL MODE")
                self.in_emergency_mode = False
            
            return self.adaptive_controller.update(intersection_state, current_time)
    
    def get_status(self) -> dict:
        """Get controller status for monitoring"""
        emergency_info = self.emergency_controller.get_state_info()
        
        return {
            'mode': 'EMERGENCY' if self.in_emergency_mode else 'NORMAL',
            'emergency_state': emergency_info['state'],
            'emergency_active': emergency_info['is_active'],
            'emergency_approach': emergency_info['emergency_approach'],
            'emergency_distance': emergency_info['emergency_distance'],
            'emergency_phase': emergency_info['emergency_phase']
        }
    
    def reset(self):
        """Reset controller state"""
        self.adaptive_controller.reset()
        self.emergency_controller.reset()
        self.in_emergency_mode = False
