"""
Main signal controller integrating adaptive control and emergency priority.
Acts as arbiter between normal operation and emergency preemption.
"""

from control.adaptive_controller import AdaptiveController
from control.emergency_priority import EmergencyPriorityController
from control.signal_phases import PhaseType


class IntegratedSignalController:
    """
    Integrated signal controller.
    Combines adaptive control with emergency vehicle priority.
    """
    
    def __init__(self):
        """Initialize integrated controller"""
        # Normal adaptive controller
        self.adaptive_controller = AdaptiveController(
            min_green=10.0,
            max_green=60.0,
            saturation_flow=0.5
        )
        
        # Emergency priority controller
        self.emergency_controller = EmergencyPriorityController(
            detection_threshold=100.0,
            preemption_threshold=80.0,
            clearing_distance=5.0,
            cooldown_duration=10.0
        )
        
        # Mode tracking
        self.in_emergency_mode = False
        self.last_normal_phase = PhaseType.NS_THROUGH
        
        print("✓ Integrated signal controller initialized")
    
    def update(self, intersection_state, current_time: float) -> str:
        """
        Update signal control with emergency priority
        
        Args:
            intersection_state: Current traffic state
            current_time: Simulation time
            
        Returns:
            SUMO signal state string
        """
        # Check for emergency vehicles
        is_emergency, emergency_phase, emergency_status = \
            self.emergency_controller.update(intersection_state, current_time)
        
        if is_emergency:
            # EMERGENCY MODE - override normal control
            if not self.in_emergency_mode:
                print(f"⚠️  SWITCHING TO EMERGENCY MODE")
                self.in_emergency_mode = True
            
            # Force emergency phase
            # Note: This is simplified - real implementation would handle
            # transition through yellow/all-red properly
            from control.signal_phases import SignalPhaseController
            phase_controller = SignalPhaseController()
            emergency_phase_config = phase_controller.get_phase(emergency_phase)
            
            return emergency_phase_config.sumo_state_green
        
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
            'emergency_active': self.emergency_controller.is_emergency_active(),
            'emergency_approach': emergency_info.get('approach'),
            'emergency_distance': emergency_info.get('distance')
        }
    
    def reset(self):
        """Reset controller state"""
        self.adaptive_controller.reset()
        self.emergency_controller.reset()
        self.in_emergency_mode = False
