"""
Emergency vehicle priority system.
Detects approaching emergency vehicles and overrides normal signal control.
"""

from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass
from control.signal_phases import PhaseType, SignalPhaseController
from control.safety_validator import SafetyValidator


class EmergencyState(Enum):
    """Emergency priority system states"""
    NORMAL = 0           # No emergency vehicle detected
    DETECTED = 1         # Emergency vehicle detected, evaluating
    PREEMPTING = 2       # Actively changing signals for emergency vehicle
    CLEARING = 3         # Emergency vehicle passed, clearing corridor
    COOLDOWN = 4         # Post-emergency cooldown period


@dataclass
class EmergencyVehicle:
    """Emergency vehicle information"""
    track_id: int
    approach: str  # N, S, E, W
    distance: float  # Distance to stop line (meters)
    speed: float  # Speed (m/s)
    vehicle_type: str  # ambulance, fire_truck


class EmergencyPriorityController:
    """
    Emergency vehicle priority controller.
    Implements preemption logic to clear path for emergency vehicles.
    """
    
    def __init__(self,
                 detection_threshold: float = 100.0,  # Detect at 100m
                 preemption_threshold: float = 80.0,   # Start preemption at 80m
                 clearing_distance: float = 5.0,       # Clear when within 5m
                 cooldown_duration: float = 10.0):     # 10s cooldown
        """
        Initialize emergency priority controller
        
        Args:
            detection_threshold: Distance to start monitoring (meters)
            preemption_threshold: Distance to start signal preemption (meters)
            clearing_distance: Distance threshold to consider vehicle "passed" (meters)
            cooldown_duration: Duration of cooldown after emergency (seconds)
        """
        self.phase_controller = SignalPhaseController()
        self.safety_validator = SafetyValidator()
        
        self.detection_threshold = detection_threshold
        self.preemption_threshold = preemption_threshold
        self.clearing_distance = clearing_distance
        self.cooldown_duration = cooldown_duration
        
        # State tracking
        self.state = EmergencyState.NORMAL
        self.active_emergency: Optional[EmergencyVehicle] = None
        self.emergency_phase: Optional[PhaseType] = None
        
        self.state_entry_time: float = 0.0
        self.preemption_start_time: float = 0.0
        self.cooldown_start_time: float = 0.0
        
        # History for duplicate detection prevention
        self.recently_served_vehicles = set()  # track_ids
        self.recent_vehicle_timeout = 60.0  # Clear after 60s
        
        print("✓ Emergency priority controller initialized")
    
    def update(self, 
               intersection_state,
               current_time: float) -> Tuple[bool, Optional[PhaseType], str]:
        """
        Update emergency priority system
        
        Args:
            intersection_state: Current traffic state
            current_time: Current simulation time
            
        Returns:
            (is_emergency_active, emergency_phase, status_message)
        """
        # Detect emergency vehicles
        emergency_vehicle = self._detect_emergency_vehicle(intersection_state)
        
        # State machine
        if self.state == EmergencyState.NORMAL:
            return self._handle_normal_state(emergency_vehicle, current_time)
        
        elif self.state == EmergencyState.DETECTED:
            return self._handle_detected_state(emergency_vehicle, current_time)
        
        elif self.state == EmergencyState.PREEMPTING:
            return self._handle_preempting_state(emergency_vehicle, current_time)
        
        elif self.state == EmergencyState.CLEARING:
            return self._handle_clearing_state(emergency_vehicle, current_time)
        
        elif self.state == EmergencyState.COOLDOWN:
            return self._handle_cooldown_state(current_time)
        
        return False, None, "Unknown state"
    
    def _detect_emergency_vehicle(self, intersection_state) -> Optional[EmergencyVehicle]:
        """
        Detect approaching emergency vehicles
        
        Returns:
            EmergencyVehicle if detected, None otherwise
        """
        if not intersection_state.has_emergency:
            return None
        
        # Find the closest emergency vehicle
        closest_emergency = None
        min_distance = float('inf')
        
        for lane_id, lane_state in intersection_state.lane_states.items():
            if not lane_state.has_emergency_vehicle:
                continue
            
            if lane_state.emergency_vehicle_distance is None:
                continue
            
            distance = lane_state.emergency_vehicle_distance
            
            # Must be within detection threshold and approaching
            if distance <= self.detection_threshold and distance > 0:
                if distance < min_distance:
                    min_distance = distance
                    
                    # Extract approach from lane_id (e.g., "N_in_0" -> "N")
                    approach = lane_id.split('_')[0]
                    
                    # Find emergency vehicle details from lane state
                    # (This is simplified - in real system would track individual vehicles)
                    closest_emergency = EmergencyVehicle(
                        track_id=0,  # Would use real track_id
                        approach=approach,
                        distance=distance,
                        speed=lane_state.avg_speed,
                        vehicle_type="ambulance"  # Would get from detection
                    )
        
        return closest_emergency
    
    def _handle_normal_state(self, emergency_vehicle: Optional[EmergencyVehicle],
                            current_time: float) -> Tuple[bool, Optional[PhaseType], str]:
        """Handle NORMAL state - monitoring for emergency vehicles"""
        if emergency_vehicle and emergency_vehicle.distance <= self.detection_threshold:
            # Emergency vehicle detected
            self.state = EmergencyState.DETECTED
            self.active_emergency = emergency_vehicle
            self.state_entry_time = current_time
            
            print(f"\n🚨 EMERGENCY VEHICLE DETECTED")
            print(f"   Approach: {emergency_vehicle.approach}")
            print(f"   Distance: {emergency_vehicle.distance:.1f}m")
            print(f"   State: NORMAL -> DETECTED\n")
            
            return False, None, "Emergency detected"
        
        return False, None, "Normal operation"
    
    def _handle_detected_state(self, emergency_vehicle: Optional[EmergencyVehicle],
                               current_time: float) -> Tuple[bool, Optional[PhaseType], str]:
        """Handle DETECTED state - evaluate and prepare for preemption"""
        if emergency_vehicle is None:
            # False alarm, return to normal
            print("   False alarm - returning to normal")
            self.state = EmergencyState.NORMAL
            self.active_emergency = None
            return False, None, "False alarm"
        
        # Check if vehicle is close enough to start preemption
        if emergency_vehicle.distance <= self.preemption_threshold:
            # Start preemption
            self.state = EmergencyState.PREEMPTING
            self.preemption_start_time = current_time
            
            # Determine required phase
            self.emergency_phase = self._get_emergency_phase(emergency_vehicle.approach)
            
            print(f"   Distance: {emergency_vehicle.distance:.1f}m")
            print(f"   State: DETECTED -> PREEMPTING")
            print(f"   Required phase: {self.emergency_phase}\n")
            
            return True, self.emergency_phase, "Starting preemption"
        
        return False, None, f"Monitoring (dist: {emergency_vehicle.distance:.1f}m)"
    
    def _handle_preempting_state(self, emergency_vehicle: Optional[EmergencyVehicle],
                                 current_time: float) -> Tuple[bool, Optional[PhaseType], str]:
        """Handle PREEMPTING state - actively clearing path"""
        if emergency_vehicle is None:
            # Vehicle disappeared (passed through or left)
            print("   Emergency vehicle passed")
            self.state = EmergencyState.CLEARING
            self.state_entry_time = current_time
            return True, self.emergency_phase, "Clearing"
        
        # Check if vehicle has passed the stop line
        if emergency_vehicle.distance <= self.clearing_distance:
            print(f"   Vehicle cleared intersection (dist: {emergency_vehicle.distance:.1f}m)")
            self.state = EmergencyState.CLEARING
            self.state_entry_time = current_time
            
            # Mark vehicle as served
            if self.active_emergency:
                self.recently_served_vehicles.add(self.active_emergency.track_id)
            
            return True, self.emergency_phase, "Vehicle cleared"
        
        # Continue preemption
        return True, self.emergency_phase, f"Preempting (dist: {emergency_vehicle.distance:.1f}m)"
    
    def _handle_clearing_state(self, emergency_vehicle: Optional[EmergencyVehicle],
                               current_time: float) -> Tuple[bool, Optional[PhaseType], str]:
        """Handle CLEARING state - maintain clear path briefly"""
        time_in_state = current_time - self.state_entry_time
        
        # Maintain clear path for 5 seconds after vehicle passes
        if time_in_state >= 5.0:
            print("   Clearing complete - entering cooldown")
            self.state = EmergencyState.COOLDOWN
            self.cooldown_start_time = current_time
            self.active_emergency = None
            return False, None, "Entering cooldown"
        
        # Continue clearing
        return True, self.emergency_phase, f"Clearing ({5.0 - time_in_state:.1f}s remaining)"
    
    def _handle_cooldown_state(self, current_time: float) -> Tuple[bool, Optional[PhaseType], str]:
        """Handle COOLDOWN state - prevent immediate re-triggering"""
        time_in_cooldown = current_time - self.cooldown_start_time
        
        if time_in_cooldown >= self.cooldown_duration:
            print("   Cooldown complete - resuming normal operation\n")
            self.state = EmergencyState.NORMAL
            self.emergency_phase = None
            
            # Clear recently served vehicles
            if time_in_cooldown >= self.recent_vehicle_timeout:
                self.recently_served_vehicles.clear()
            
            return False, None, "Normal operation resumed"
        
        remaining = self.cooldown_duration - time_in_cooldown
        return False, None, f"Cooldown ({remaining:.1f}s remaining)"
    
    def _get_emergency_phase(self, approach: str) -> PhaseType:
        """Determine which phase is needed for emergency vehicle"""
        if approach in ['N', 'S']:
            return PhaseType.EMERGENCY_NS
        else:  # E or W
            return PhaseType.EMERGENCY_EW
    
    def is_emergency_active(self) -> bool:
        """Check if emergency preemption is currently active"""
        return self.state in [EmergencyState.PREEMPTING, EmergencyState.CLEARING]
    
    def get_state_info(self) -> dict:
        """Get current state information for logging"""
        return {
            'state': self.state.name,
            'has_active_emergency': self.active_emergency is not None,
            'emergency_phase': self.emergency_phase.name if self.emergency_phase else None,
            'approach': self.active_emergency.approach if self.active_emergency else None,
            'distance': self.active_emergency.distance if self.active_emergency else None
        }
    
    def reset(self):
        """Reset emergency priority system"""
        self.state = EmergencyState.NORMAL
        self.active_emergency = None
        self.emergency_phase = None
        self.recently_served_vehicles.clear()
