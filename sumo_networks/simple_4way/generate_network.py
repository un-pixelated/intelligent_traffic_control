"""
Generate a simple 4-way intersection network for SUMO.
Creates road network, traffic lights, and basic routes.
"""

import os
import subprocess
from pathlib import Path

def create_nodes_file():
    """Create node definitions (intersection points)"""
    nodes_xml = """<?xml version="1.0" encoding="UTF-8"?>
<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
       xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    
    <!-- Central intersection -->
    <node id="center" x="0.0" y="0.0" type="traffic_light"/>
    
    <!-- Approach nodes (100m from center) -->
    <node id="north" x="0.0" y="100.0" type="priority"/>
    <node id="south" x="0.0" y="-100.0" type="priority"/>
    <node id="east" x="100.0" y="0.0" type="priority"/>
    <node id="west" x="-100.0" y="0.0" type="priority"/>
    
    <!-- Exit nodes (100m from center, opposite direction) -->
    <node id="north_end" x="0.0" y="200.0" type="priority"/>
    <node id="south_end" x="0.0" y="-200.0" type="priority"/>
    <node id="east_end" x="200.0" y="0.0" type="priority"/>
    <node id="west_end" x="-200.0" y="0.0" type="priority"/>
    
</nodes>
"""
    with open('network.nod.xml', 'w') as f:
        f.write(nodes_xml)
    print("✓ Created network.nod.xml")


def create_edges_file():
    """Create edge definitions (road segments)"""
    edges_xml = """<?xml version="1.0" encoding="UTF-8"?>
<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
       xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    
    <!-- Incoming edges (3 lanes each: 2 through + 1 left turn) -->
    <edge id="N_in" from="north" to="center" numLanes="3" speed="13.89">
        <lane index="0" allow="all"/>  <!-- Right/through -->
        <lane index="1" allow="all"/>  <!-- Through -->
        <lane index="2" allow="all"/>  <!-- Left turn -->
    </edge>
    
    <edge id="S_in" from="south" to="center" numLanes="3" speed="13.89">
        <lane index="0" allow="all"/>
        <lane index="1" allow="all"/>
        <lane index="2" allow="all"/>
    </edge>
    
    <edge id="E_in" from="east" to="center" numLanes="3" speed="13.89">
        <lane index="0" allow="all"/>
        <lane index="1" allow="all"/>
        <lane index="2" allow="all"/>
    </edge>
    
    <edge id="W_in" from="west" to="center" numLanes="3" speed="13.89">
        <lane index="0" allow="all"/>
        <lane index="1" allow="all"/>
        <lane index="2" allow="all"/>
    </edge>
    
    <!-- Outgoing edges (2 lanes each) -->
    <edge id="N_out" from="center" to="north_end" numLanes="2" speed="13.89"/>
    <edge id="S_out" from="center" to="south_end" numLanes="2" speed="13.89"/>
    <edge id="E_out" from="center" to="east_end" numLanes="2" speed="13.89"/>
    <edge id="W_out" from="center" to="west_end" numLanes="2" speed="13.89"/>
    
</edges>
"""
    with open('network.edg.xml', 'w') as f:
        f.write(edges_xml)
    print("✓ Created network.edg.xml")


def create_connections_file():
    """Define allowed turns at intersection"""
    connections_xml = """<?xml version="1.0" encoding="UTF-8"?>
<connections xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
             xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/connections_file.xsd">
    
    <!-- North approach -->
    <connection from="N_in" to="S_out" fromLane="0" toLane="0"/>  <!-- Through -->
    <connection from="N_in" to="S_out" fromLane="1" toLane="1"/>  <!-- Through -->
    <connection from="N_in" to="E_out" fromLane="2" toLane="0"/>  <!-- Left turn -->
    
    <!-- South approach -->
    <connection from="S_in" to="N_out" fromLane="0" toLane="0"/>
    <connection from="S_in" to="N_out" fromLane="1" toLane="1"/>
    <connection from="S_in" to="W_out" fromLane="2" toLane="0"/>
    
    <!-- East approach -->
    <connection from="E_in" to="W_out" fromLane="0" toLane="0"/>
    <connection from="E_in" to="W_out" fromLane="1" toLane="1"/>
    <connection from="E_in" to="S_out" fromLane="2" toLane="0"/>
    
    <!-- West approach -->
    <connection from="W_in" to="E_out" fromLane="0" toLane="0"/>
    <connection from="W_in" to="E_out" fromLane="1" toLane="1"/>
    <connection from="W_in" to="N_out" fromLane="2" toLane="0"/>
    
</connections>
"""
    with open('network.con.xml', 'w') as f:
        f.write(connections_xml)
    print("✓ Created network.con.xml")


def create_traffic_light_file():
    """Define traffic light phases"""
    tls_xml = """<?xml version="1.0" encoding="UTF-8"?>
<additional xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/additional_file.xsd">
    
    <tlLogic id="center" type="static" programID="0" offset="0">
        <!-- Phase 0: North-South through (green) -->
        <phase duration="30" state="GGGrrrGGGrrr"/>
        <!-- Yellow transition -->
        <phase duration="3" state="yyyrrryyyrrr"/>
        
        <!-- Phase 1: East-West through (green) -->
        <phase duration="30" state="rrrGGGrrrGGG"/>
        <!-- Yellow transition -->
        <phase duration="3" state="rrryyyrrryyy"/>
    </tlLogic>
    
</additional>
"""
    with open('traffic_lights.add.xml', 'w') as f:
        f.write(tls_xml)
    print("✓ Created traffic_lights.add.xml")


def build_network():
    """Use netconvert to build the network"""
    cmd = [
        'netconvert',
        '--node-files=network.nod.xml',
        '--edge-files=network.edg.xml',
        '--connection-files=network.con.xml',
        '--tllogic-files=traffic_lights.add.xml',
        '--output-file=network.net.xml',
        '--no-turnarounds=true',
        '--junctions.corner-detail=5',
        
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Built network.net.xml")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error building network: {e.stderr}")
        return False


def create_route_file():
    """Create traffic demand (routes and flows)"""
    routes_xml = """<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
        xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    
    <!-- Vehicle types -->
    <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="5.0" 
           minGap="2.5" maxSpeed="50" guiShape="passenger"/>
    <vType id="truck" accel="1.8" decel="4.0" sigma="0.5" length="12.0" 
           minGap="3.0" maxSpeed="40" guiShape="truck"/>
    <vType id="ambulance" accel="3.0" decel="5.0" sigma="0.3" length="6.0" 
           minGap="2.5" maxSpeed="50" guiShape="emergency" color="1,0,0"/>
    <vType id="fire_truck" accel="2.5" decel="4.5" sigma="0.3" length="8.0" 
           minGap="3.0" maxSpeed="45" guiShape="firebrigade" color="1,0,0"/>
    
    <!-- Routes (all possible paths through intersection) -->
    <!-- North to South (through) -->
    <route id="N_S" edges="N_in S_out"/>
    <!-- North to East (left turn) -->
    <route id="N_E" edges="N_in E_out"/>
    
    <!-- South to North -->
    <route id="S_N" edges="S_in N_out"/>
    <!-- South to West -->
    <route id="S_W" edges="S_in W_out"/>
    
    <!-- East to West -->
    <route id="E_W" edges="E_in W_out"/>
    <!-- East to South -->
    <route id="E_S" edges="E_in S_out"/>
    
    <!-- West to East -->
    <route id="W_E" edges="W_in E_out"/>
    <!-- West to North -->
    <route id="W_N" edges="W_in N_out"/>
    
    <!-- Traffic flows (vehicles/hour) -->
    <!-- Normal traffic (80% through, 20% turning) -->
    <flow id="flow_N_S" type="car" route="N_S" begin="0" end="3600" 
          vehsPerHour="300" departSpeed="max"/>
    <flow id="flow_N_E" type="car" route="N_E" begin="0" end="3600" 
          vehsPerHour="75" departSpeed="max"/>
    
    <flow id="flow_S_N" type="car" route="S_N" begin="0" end="3600" 
          vehsPerHour="300" departSpeed="max"/>
    <flow id="flow_S_W" type="car" route="S_W" begin="0" end="3600" 
          vehsPerHour="75" departSpeed="max"/>
    
    <flow id="flow_E_W" type="car" route="E_W" begin="0" end="3600" 
          vehsPerHour="250" departSpeed="max"/>
    <flow id="flow_E_S" type="car" route="E_S" begin="0" end="3600" 
          vehsPerHour="60" departSpeed="max"/>
    
    <flow id="flow_W_E" type="car" route="W_E" begin="0" end="3600" 
          vehsPerHour="250" departSpeed="max"/>
    <flow id="flow_W_N" type="car" route="W_N" begin="0" end="3600" 
          vehsPerHour="60" departSpeed="max"/>
    
    <!-- Occasional trucks (5% of traffic) -->
    <flow id="flow_trucks_N" type="truck" route="N_S" begin="0" end="3600" 
          vehsPerHour="20" departSpeed="max"/>
    <flow id="flow_trucks_E" type="truck" route="E_W" begin="0" end="3600" 
          vehsPerHour="15" departSpeed="max"/>
    
    <!-- Emergency vehicles (rare, specific scenarios) -->
    <!-- We'll inject these programmatically during simulation -->
    
</routes>
"""
    with open('routes.rou.xml', 'w') as f:
        f.write(routes_xml)
    print("✓ Created routes.rou.xml")


def create_sumo_config():
    """Create SUMO configuration file"""
    config_xml = """<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    
    <input>
        <net-file value="network.net.xml"/>
        <route-files value="routes.rou.xml"/>
    </input>
    
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="0.1"/>
    </time>
    
    <processing>
        <time-to-teleport value="-1"/>
        <max-depart-delay value="300"/>
    </processing>
    
    <report>
        <verbose value="false"/>
        <no-step-log value="true"/>
    </report>
    
    <gui_only>
        <start value="true"/>
    </gui_only>
    
</configuration>
"""
    with open('sumo.cfg', 'w') as f:
        f.write(config_xml)
    print("✓ Created sumo.cfg")


def main():
    """Generate complete SUMO network"""
    print("Generating SUMO network for 4-way intersection...\n")
    
    # Change to network directory
    network_dir = Path(__file__).parent
    os.chdir(network_dir)
    
    # Create all files
    create_nodes_file()
    create_edges_file()
    create_connections_file()
    create_traffic_light_file()
    
    # Build network
    if build_network():
        create_route_file()
        create_sumo_config()
        print("\n✓ Network generation complete!")
        print(f"  Location: {network_dir}")
        print("\nTo visualize:")
        print("  sumo-gui -c sumo.cfg")
    else:
        print("\n✗ Network generation failed")
        return False
    
    return True


if __name__ == "__main__":
    main()