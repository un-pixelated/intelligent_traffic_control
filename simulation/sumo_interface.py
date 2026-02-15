"""
SUMO simulation interface using TraCI.
Handles simulation control, vehicle queries, and signal manipulation.
"""

import os
import sys
import traci
import sumolib
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class VehicleInfo:
    """Vehicle state information from SUMO"""
    id: str
    type: str  # vType
    position: Tuple[float, float]  # (x, y) in meters
    speed: float  # m/s
    angle: float  # degrees
    lane_id: str
    distance_to_intersection: float
    waiting_time: float  # seconds stopped


class SUMOInterface:
    """Interface to SUMO simulation via TraCI"""
    
    def __init__(self, config_file: str, use_gui: bool = False):
        """
        Initialize SUMO connection
        
        Args:
            config_file: Path to sumo.cfg file
            use_gui: Whether to use sumo-gui (visual) or sumo (headless)
        """
        self.config_file = config_file
        self.use_gui = use_gui
        self.connected = False
        self.step_count = 0
        
        # Get network directory
        self.network_dir = os.path.dirname(config_file)
        self.net_file = os.path.join(self.network_dir, 'network.net.xml')
        
        # Load network for geometric queries
        self.net = sumolib.net.readNet(self.net_file)
        
        # Get intersection node
        self.intersection_node = self.net.getNode('center')
        self.intersection_pos = (
            self.intersection_node.getCoord()[0],
            self.intersection_node.getCoord()[1]
        )
        
        print(f"SUMO network loaded: {self.net_file}")
        print(f"Intersection position: {self.intersection_pos}")
    
    def start(self, port: int = 8813):
        """Start SUMO simulation"""
        sumo_binary = "sumo-gui" if self.use_gui else "sumo"
        
        sumo_cmd = [
            sumo_binary,
            "-c", self.config_file,
            "--step-length", "0.1",
            "--time-to-teleport", "-1",
            "--no-step-log",
            "--no-warnings",
            "--random"
        ]
        
        try:
            traci.start(sumo_cmd, port=port)
            self.connected = True
            self.step_count = 0
            print(f"✓ SUMO started ({sumo_binary})")
        except Exception as e:
            print(f"✗ Failed to start SUMO: {e}")
            raise
    
    def step(self):
        """Advance simulation by one step"""
        if not self.connected:
            raise RuntimeError("SUMO not connected")
        
        traci.simulationStep()
        self.step_count += 1
    
    def close(self):
        """Close SUMO connection"""
        if self.connected:
            traci.close()
            self.connected = False
            print("✓ SUMO connection closed")
    
    def get_current_time(self) -> float:
        """Get simulation time in seconds"""
        return traci.simulation.getTime()
    
    def get_all_vehicles(self) -> List[VehicleInfo]:
        """Get information for all vehicles in simulation"""
        vehicle_ids = traci.vehicle.getIDList()
        vehicles = []
        
        for vid in vehicle_ids:
            try:
                pos = traci.vehicle.getPosition(vid)
                lane_id = traci.vehicle.getLaneID(vid)
                
                # Calculate distance to intersection
                dist = np.sqrt(
                    (pos[0] - self.intersection_pos[0])**2 + 
                    (pos[1] - self.intersection_pos[1])**2
                )
                
                vehicle = VehicleInfo(
                    id=vid,
                    type=traci.vehicle.getTypeID(vid),
                    position=pos,
                    speed=traci.vehicle.getSpeed(vid),
                    angle=traci.vehicle.getAngle(vid),
                    lane_id=lane_id,
                    distance_to_intersection=dist,
                    waiting_time=traci.vehicle.getWaitingTime(vid)
                )
                vehicles.append(vehicle)
            except traci.exceptions.TraCIException:
                continue  # Vehicle may have left simulation
        
        return vehicles
    
    def get_vehicles_on_lane(self, lane_id: str) -> List[VehicleInfo]:
        """Get all vehicles on a specific lane"""
        all_vehicles = self.get_all_vehicles()
        return [v for v in all_vehicles if v.lane_id == lane_id]
    
    def get_traffic_light_state(self, tls_id: str = "center") -> str:
        """Get current traffic light state string"""
        return traci.trafficlight.getRedYellowGreenState(tls_id)
    
    def set_traffic_light_state(self, state: str, tls_id: str = "center"):
        """
        Set traffic light state
        
        Args:
            state: State string (e.g., 'GGGrrrGGGrrr')
                  G=green, y=yellow, r=red for each connection
            tls_id: Traffic light ID
        """
        traci.trafficlight.setRedYellowGreenState(tls_id, state)
    
    def set_traffic_light_phase(self, phase_index: int, tls_id: str = "center"):
        """Set traffic light to specific phase"""
        traci.trafficlight.setPhase(tls_id, phase_index)
    
    def get_lane_vehicles_count(self, lane_id: str) -> int:
        """Get number of vehicles on lane"""
        try:
            return traci.lane.getLastStepVehicleNumber(lane_id)
        except traci.exceptions.TraCIException:
            return 0
    
    def get_lane_occupancy(self, lane_id: str) -> float:
        """Get lane occupancy percentage (0-100)"""
        try:
            return traci.lane.getLastStepOccupancy(lane_id)
        except traci.exceptions.TraCIException:
            return 0.0
    
    def get_lane_mean_speed(self, lane_id: str) -> float:
        """Get mean speed on lane (m/s)"""
        try:
            return traci.lane.getLastStepMeanSpeed(lane_id)
        except traci.exceptions.TraCIException:
            return 0.0
    
    def add_emergency_vehicle(self, 
                            route_id: str, 
                            vtype: str = "ambulance",
                            depart_time: Optional[float] = None):
        """
        Add an emergency vehicle to simulation
        
        Args:
            route_id: Route to follow (e.g., 'N_S')
            vtype: Vehicle type ('ambulance' or 'fire_truck')
            depart_time: When to depart (None = now)
        """
        vid = f"emergency_{self.step_count}_{vtype}"
        
        try:
            traci.vehicle.add(
                vehID=vid,
                routeID=route_id,
                typeID=vtype,
                depart=depart_time if depart_time else 'now'
            )
            print(f"✓ Added emergency vehicle: {vid} on route {route_id}")
            return vid
        except traci.exceptions.TraCIException as e:
            print(f"✗ Failed to add emergency vehicle: {e}")
            return None
    
    def get_network_bounds(self) -> Tuple[float, float, float, float]:
        """Get network bounding box (min_x, min_y, max_x, max_y)"""
        boundary = self.net.getBoundary()
        return boundary
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()