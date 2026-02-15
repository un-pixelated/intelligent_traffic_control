"""
Day 3: Emergency Vehicle Priority Controller

Deterministic finite state machine for emergency vehicle preemption.
This controller has absolute priority when active.

Architecture:
    - Circuit breaker pattern: overrides normal controller when active
    - Deterministic state machine (5 states, no learning)
    - Conservative and safety-first
    - Uses only IntersectionState (no raw perception)

State Machine:
    NORMAL -> DETECTED -> PREEMPTING -> CLEARING -> COOLDOWN -> NORMAL

Author: Day 3 Implementation
Date: 2026-02-15
Status: PRODUCTION
"""

from enum import Enum
from typing import Optional
from control.signal_phases import PhaseType


class EmergencyState(Enum):
    """
    Emergency priority system states - MANDATORY, DO NOT ADD MORE.
    
    State machine is a safety-critical system.
    """
    NORMAL = 0       # No emergency active, pass-through mode
    DETECTED = 1     # Emergency detected, debouncing
    PREEMPTING = 2   # Forcing emergency phase
    CLEARING = 3     # Emergency passed, flushing intersection
    COOLDOWN = 4     # Preventing oscillation


class EmergencyPriorityController:
    """
    Emergency Vehicle Priority Controller - Day 3 Implementation.
    
    Deterministic finite state machine that overrides normal signal control
    when emergency vehicles are detected.
    
    Contract:
        - Input: IntersectionState + timestamp
        - Output: (is_active, emergency_phase_override)
        - No side effects
        - No SUMO calls
        - No perception access
        
    Behavior:
        - NORMAL: Pass-through, normal controller runs
        - Emergency detected: Override everything
        - Emergency cleared: Return control cleanly
        
    Timing Parameters (Conservative):
        - DETECTION_THRESHOLD: 100m (when to start monitoring)
        - PREEMPTION_THRESHOLD: 80m (when to force phase change)
        - CLEARING_DISTANCE: 5m (when vehicle has "passed")
        - CLEARANCE_TIME: 5.0s (how long to hold after passing)
        - COOLDOWN_TIME: 10.0s (prevent immediate re-trigger)
    """
    
    # ========== TIMING PARAMETERS (FROZEN) ==========
    
    # Detection threshold: Start monitoring at 100m
    # Justification: Gives ample time for state machine transitions
    DETECTION_THRESHOLD = 100.0  # meters
    
    # Preemption threshold: Force phase change at 80m
    # Justification: Balance between safety margin and responsiveness
    PREEMPTION_THRESHOLD = 80.0  # meters
    
    # Clearing distance: Vehicle has "passed" at 5m
    # Justification: Far enough through intersection to be clear
    CLEARING_DISTANCE = 5.0  # meters
    
    # Clearance time: Hold phase for 5 seconds after passing
    # Justification: Ensures no conflicting traffic enters corridor
    CLEARANCE_TIME = 5.0  # seconds
    
    # Cooldown time: Ignore new emergencies for 10 seconds
    # Justification: Prevents oscillation from same vehicle
    COOLDOWN_TIME = 10.0  # seconds
    
    def __init__(self):
        """
        Initialize emergency priority controller.
        
        No parameters - all thresholds are frozen constants.
        """
        # State machine
        self.state = EmergencyState.NORMAL
        
        # Active emergency tracking
        self.emergency_approach: Optional[str] = None  # N, S, E, W
        self.emergency_distance: Optional[float] = None
        self.emergency_phase: Optional[PhaseType] = None
        
        # Timing
        self.state_entry_time: float = 0.0
        
        print("✓ Emergency Priority Controller initialized")
        print(f"  Detection threshold: {self.DETECTION_THRESHOLD}m")
        print(f"  Preemption threshold: {self.PREEMPTION_THRESHOLD}m")
        print(f"  Clearance time: {self.CLEARANCE_TIME}s")
        print(f"  Cooldown time: {self.COOLDOWN_TIME}s")
    
    def update(self, intersection_state, current_time: float):
        """
        Update emergency priority system state machine.
        
        This method updates internal state only. Call get_signal_command()
        to retrieve the control decision.
        
        Args:
            intersection_state: IntersectionState (frozen, from state estimation)
            current_time: Simulation time (seconds)
            
        Side Effects:
            - Updates self.state
            - Updates emergency tracking variables
            - Logs state transitions
            
        Does NOT return signal command (see get_signal_command()).
        """
        # Detect closest emergency vehicle
        has_emergency, approach, distance = self._detect_emergency(intersection_state)
        
        # State machine dispatch
        if self.state == EmergencyState.NORMAL:
            self._update_normal(has_emergency, approach, distance, current_time)
        
        elif self.state == EmergencyState.DETECTED:
            self._update_detected(has_emergency, approach, distance, current_time)
        
        elif self.state == EmergencyState.PREEMPTING:
            self._update_preempting(has_emergency, approach, distance, current_time)
        
        elif self.state == EmergencyState.CLEARING:
            self._update_clearing(current_time)
        
        elif self.state == EmergencyState.COOLDOWN:
            self._update_cooldown(current_time)
    
    def get_signal_command(self):
        """
        Get signal control command.
        
        Returns:
            (is_active, emergency_phase_override)
            
            is_active: True if emergency controller should override normal controller
            emergency_phase_override: PhaseType to force, or None if not active
            
        Usage by IntegratedSignalController:
            is_active, emergency_phase = emergency_controller.get_signal_command()
            if is_active:
                return emergency_phase_sumo_state
            else:
                return normal_controller.get_signal_command()
        """
        if self.state in [EmergencyState.PREEMPTING, EmergencyState.CLEARING]:
            # Emergency controller is active
            return True, self.emergency_phase
        else:
            # Pass through to normal controller
            return False, None
    
    def reset(self):
        """
        Reset controller to initial state.
        
        Used at start of new simulation episode.
        """
        self.state = EmergencyState.NORMAL
        self.emergency_approach = None
        self.emergency_distance = None
        self.emergency_phase = None
        self.state_entry_time = 0.0
    
    # ========== STATE MACHINE TRANSITIONS ==========
    
    def _update_normal(self, has_emergency: bool, approach: Optional[str],
                      distance: Optional[float], current_time: float):
        """
        NORMAL state handler.
        
        Behavior:
            - Monitor for emergency vehicles
            - Pass-through mode (normal controller runs)
            
        Exit condition:
            - Emergency detected within DETECTION_THRESHOLD
        """
        if has_emergency and distance is not None and distance <= self.DETECTION_THRESHOLD:
            # Transition: NORMAL -> DETECTED
            self.state = EmergencyState.DETECTED
            self.state_entry_time = current_time
            self.emergency_approach = approach
            self.emergency_distance = distance
            
            self._log_transition("NORMAL", "DETECTED", 
                               f"Emergency detected: {approach} @ {distance:.1f}m")
    
    def _update_detected(self, has_emergency: bool, approach: Optional[str],
                        distance: Optional[float], current_time: float):
        """
        DETECTED state handler.
        
        Behavior:
            - Debounce / confirmation period
            - Monitor emergency vehicle approach
            
        Exit conditions:
            - Emergency within PREEMPTION_THRESHOLD -> PREEMPTING
            - Emergency disappeared -> NORMAL (false alarm)
        """
        if not has_emergency or distance is None:
            # Transition: DETECTED -> NORMAL (false alarm)
            self.state = EmergencyState.NORMAL
            self.emergency_approach = None
            self.emergency_distance = None
            
            self._log_transition("DETECTED", "NORMAL", "False alarm - no emergency")
            return
        
        # Update tracking
        self.emergency_approach = approach
        self.emergency_distance = distance
        
        if distance <= self.PREEMPTION_THRESHOLD:
            # Transition: DETECTED -> PREEMPTING
            self.state = EmergencyState.PREEMPTING
            self.state_entry_time = current_time
            self.emergency_phase = self._get_emergency_phase(approach)
            
            self._log_transition("DETECTED", "PREEMPTING",
                               f"Distance {distance:.1f}m <= {self.PREEMPTION_THRESHOLD}m, "
                               f"forcing {self.emergency_phase.name}")
    
    def _update_preempting(self, has_emergency: bool, approach: Optional[str],
                          distance: Optional[float], current_time: float):
        """
        PREEMPTING state handler.
        
        Behavior:
            - Force emergency phase
            - Ignore normal controller completely
            - Maintain until vehicle passes
            
        Exit conditions:
            - Emergency within CLEARING_DISTANCE -> CLEARING (passed stop line)
            - Emergency disappeared -> CLEARING (exited range or passed)
        """
        if not has_emergency or distance is None:
            # Vehicle disappeared (passed through or left range)
            # Transition: PREEMPTING -> CLEARING
            self.state = EmergencyState.CLEARING
            self.state_entry_time = current_time
            
            self._log_transition("PREEMPTING", "CLEARING",
                               "Emergency vehicle left detection range")
            return
        
        # Update tracking
        self.emergency_distance = distance
        
        if distance <= self.CLEARING_DISTANCE:
            # Transition: PREEMPTING -> CLEARING
            self.state = EmergencyState.CLEARING
            self.state_entry_time = current_time
            
            self._log_transition("PREEMPTING", "CLEARING",
                               f"Vehicle cleared stop line (dist={distance:.1f}m)")
    
    def _update_clearing(self, current_time: float):
        """
        CLEARING state handler.
        
        Behavior:
            - Hold emergency phase briefly
            - Flush intersection safely
            - Prevent conflicting traffic from entering corridor
            
        Exit condition:
            - CLEARANCE_TIME elapsed -> COOLDOWN
        """
        time_in_state = current_time - self.state_entry_time
        
        if time_in_state >= self.CLEARANCE_TIME:
            # Transition: CLEARING -> COOLDOWN
            self.state = EmergencyState.COOLDOWN
            self.state_entry_time = current_time
            
            self._log_transition("CLEARING", "COOLDOWN",
                               f"Clearance complete ({self.CLEARANCE_TIME}s)")
    
    def _update_cooldown(self, current_time: float):
        """
        COOLDOWN state handler.
        
        Behavior:
            - Normal controller resumes
            - Emergency detection ignored (prevents oscillation)
            - System stabilizes
            
        Exit condition:
            - COOLDOWN_TIME elapsed -> NORMAL
        """
        time_in_state = current_time - self.state_entry_time
        
        if time_in_state >= self.COOLDOWN_TIME:
            # Transition: COOLDOWN -> NORMAL
            self.state = EmergencyState.NORMAL
            self.emergency_approach = None
            self.emergency_distance = None
            self.emergency_phase = None
            
            self._log_transition("COOLDOWN", "NORMAL",
                               f"Cooldown complete ({self.COOLDOWN_TIME}s)")
    
    # ========== HELPER METHODS ==========
    
    def _detect_emergency(self, intersection_state):
        """
        Detect closest emergency vehicle from intersection state.
        
        Uses only IntersectionState (no raw perception access).
        
        Args:
            intersection_state: IntersectionState from state estimation
            
        Returns:
            (has_emergency, approach, distance)
            
            has_emergency: True if any emergency vehicle detected
            approach: 'N', 'S', 'E', or 'W' (or None)
            distance: Distance to stop line in meters (or None)
            
        Rules:
            - Use intersection_state.has_emergency first (fast check)
            - Find closest emergency vehicle across all lanes
            - Multiple emergencies: choose closest
            - Invalid data: return (False, None, None)
        """
        # Fast path: no emergencies
        if not intersection_state.has_emergency:
            return False, None, None
        
        # Find closest emergency vehicle
        closest_approach = None
        closest_distance = float('inf')
        
        for lane_id, lane_state in intersection_state.lane_states.items():
            if not lane_state.has_emergency_vehicle:
                continue
            
            if lane_state.emergency_vehicle_distance is None:
                continue
            
            distance = lane_state.emergency_vehicle_distance
            
            # Must be positive (approaching, not behind stop line)
            if distance > 0 and distance < closest_distance:
                closest_distance = distance
                # Extract approach from lane_id: "N_in_0" -> "N"
                closest_approach = lane_id.split('_')[0]
        
        if closest_approach is None:
            # No valid emergency vehicle found
            return False, None, None
        
        return True, closest_approach, closest_distance
    
    def _get_emergency_phase(self, approach: str) -> PhaseType:
        """
        Determine emergency phase for given approach.
        
        Emergency phases are predefined and conflict-free.
        
        Args:
            approach: 'N', 'S', 'E', or 'W'
            
        Returns:
            PhaseType.EMERGENCY_NS or PhaseType.EMERGENCY_EW
            
        Logic:
            - North/South emergencies -> EMERGENCY_NS (clears N-S corridor)
            - East/West emergencies -> EMERGENCY_EW (clears E-W corridor)
        """
        if approach in ['N', 'S']:
            return PhaseType.EMERGENCY_NS
        else:  # E or W
            return PhaseType.EMERGENCY_EW
    
    def _log_transition(self, from_state: str, to_state: str, reason: str):
        """
        Log state transition.
        
        Args:
            from_state: Source state name
            to_state: Destination state name
            reason: Transition reason / condition met
        """
        print(f"🚨 EMERGENCY STATE: {from_state} -> {to_state}")
        print(f"   Reason: {reason}")
    
    # ========== QUERY METHODS ==========
    
    def is_active(self) -> bool:
        """
        Check if emergency controller is currently active.
        
        Returns:
            True if overriding normal controller
            
        Active states: PREEMPTING, CLEARING
        Inactive states: NORMAL, DETECTED, COOLDOWN
        """
        return self.state in [EmergencyState.PREEMPTING, EmergencyState.CLEARING]
    
    def get_state_info(self) -> dict:
        """
        Get current state information for monitoring/logging.
        
        Returns:
            Dictionary with state machine status
        """
        return {
            'state': self.state.name,
            'is_active': self.is_active(),
            'emergency_approach': self.emergency_approach,
            'emergency_distance': self.emergency_distance,
            'emergency_phase': self.emergency_phase.name if self.emergency_phase else None
        }

