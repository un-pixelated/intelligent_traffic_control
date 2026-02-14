"""
Traffic signal phase definitions and transitions.
"""

from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum


class PhaseType(Enum):
    """Signal phase types"""
    NS_THROUGH = 0      # North-South through traffic
    EW_THROUGH = 1      # East-West through traffic
    NS_LEFT = 2         # North-South left turns
    EW_LEFT = 3         # East-West left turns
    ALL_RED = 4         # All red (clearance)
    EMERGENCY_NS = 5    # Emergency: Clear N-S corridor
    EMERGENCY_EW = 6    # Emergency: Clear E-W corridor


@dataclass
class SignalPhase:
    """Signal phase configuration"""
    phase_type: PhaseType
    phase_id: int
    green_approaches: List[str]  # Which approaches get green
    min_duration: float  # Minimum green time (seconds)
    max_duration: float  # Maximum green time (seconds)
    yellow_duration: float  # Yellow time (seconds)
    all_red_duration: float  # All-red clearance time (seconds)
    
    # SUMO signal state string (12 connections)
    # Format: GGGrrrGGGrrr where each char is G/y/r for a connection
    # Connections order: N_through(3), E_through(3), S_through(3), W_through(3)
    sumo_state_green: str
    sumo_state_yellow: str
    sumo_state_red: str = "rrrrrrrrrrrr"


class SignalPhaseController:
    """Manages signal phases and transitions"""
    
    def __init__(self):
        # Define standard phases
        self.phases = {
            PhaseType.NS_THROUGH: SignalPhase(
                phase_type=PhaseType.NS_THROUGH,
                phase_id=0,
                green_approaches=['N', 'S'],
                min_duration=10.0,
                max_duration=60.0,
                yellow_duration=3.0,
                all_red_duration=2.0,
                sumo_state_green="GGGrrrGGGrrr",   # N and S green
                sumo_state_yellow="yyyrrryyyrrr"
            ),
            PhaseType.EW_THROUGH: SignalPhase(
                phase_type=PhaseType.EW_THROUGH,
                phase_id=1,
                green_approaches=['E', 'W'],
                min_duration=10.0,
                max_duration=60.0,
                yellow_duration=3.0,
                all_red_duration=2.0,
                sumo_state_green="rrrGGGrrrGGG",   # E and W green
                sumo_state_yellow="rrryyyrrryyy"
            ),
            PhaseType.EMERGENCY_NS: SignalPhase(
                phase_type=PhaseType.EMERGENCY_NS,
                phase_id=5,
                green_approaches=['N', 'S'],
                min_duration=15.0,
                max_duration=120.0,
                yellow_duration=3.0,
                all_red_duration=2.0,
                sumo_state_green="GGGrrrGGGrrr",
                sumo_state_yellow="yyyrrryyyrrr"
            ),
            PhaseType.EMERGENCY_EW: SignalPhase(
                phase_type=PhaseType.EMERGENCY_EW,
                phase_id=6,
                green_approaches=['E', 'W'],
                min_duration=15.0,
                max_duration=120.0,
                yellow_duration=3.0,
                all_red_duration=2.0,
                sumo_state_green="rrrGGGrrrGGG",
                sumo_state_yellow="rrryyyrrryyy"
            )
        }
        
        self.current_phase: PhaseType = PhaseType.NS_THROUGH
        self.phase_start_time: float = 0.0
        self.phase_elapsed: float = 0.0
        self.in_yellow: bool = False
        self.in_all_red: bool = False
        
        print("✓ Signal phase controller initialized")
    
    def get_phase(self, phase_type: PhaseType) -> SignalPhase:
        """Get phase configuration"""
        return self.phases[phase_type]
    
    def can_transition(self, current_time: float, min_green_override: bool = False) -> bool:
        """Check if phase can transition"""
        self.phase_elapsed = current_time - self.phase_start_time
        
        if self.in_yellow or self.in_all_red:
            return False  # Already in transition
        
        current_phase = self.phases[self.current_phase]
        
        if min_green_override:
            return True  # Emergency override
        
        # Must satisfy minimum green time
        return self.phase_elapsed >= current_phase.min_duration
    
    def get_next_phase(self, emergency_phase: PhaseType = None) -> PhaseType:
        """Determine next phase"""
        if emergency_phase:
            return emergency_phase
        
        # Simple two-phase cycling: NS <-> EW
        if self.current_phase == PhaseType.NS_THROUGH:
            return PhaseType.EW_THROUGH
        else:
            return PhaseType.NS_THROUGH
    
    def get_sumo_state(self) -> str:
        """Get current SUMO signal state string"""
        phase = self.phases[self.current_phase]
        
        if self.in_yellow:
            return phase.sumo_state_yellow
        elif self.in_all_red:
            return phase.sumo_state_red
        else:
            return phase.sumo_state_green
