#!/usr/bin/env python3
"""
Offscreen SUMO simulation renderer with Adaptive + Emergency controller.

Renders simulation to PNG sequence and creates MP4 video.
Works headlessly on macOS.

Corrected Day 3.5: Fixed to use SumoPerceptionAdapter instead of removed GroundTruthPerception

Usage:
    python scripts/render_simulation.py

Output:
    output/frames/frame_XXXXXX.png
    output/adaptive_emergency_demo.mp4
"""

import sys
from pathlib import Path
import subprocess
import time as time_module

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from simulation.sumo_interface import SUMOInterface
from simulation.annotated_camera import AnnotatedCamera
from perception.sumo_adapter import SumoPerceptionAdapter
from perception.lane_mapper import LaneMapper
from state_estimation.state_estimator import TrafficStateEstimator
from control.signal_controller import IntegratedSignalController


class SimulationRenderer:
    """Renders SUMO simulation with controller to video"""
    
    def __init__(self, duration: float = 120.0):
        """
        Initialize renderer
        
        Args:
            duration: Simulation duration in seconds
        """
        self.duration = duration
        
        # Paths
        self.config_file = str(project_root / "sumo_networks" / "simple_4way" / "sumo.cfg")
        self.intersection_config = str(project_root / "config" / "intersection_config.yaml")
        
        # Output directories
        self.output_dir = project_root / "output"
        self.frames_dir = self.output_dir / "frames"
        self.video_path = self.output_dir / "adaptive_emergency_demo.mp4"
        
        # Create output directories
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        
        print("="*70)
        print("OFFSCREEN SIMULATION RENDERER")
        print("="*70)
        print(f"Duration: {duration}s")
        print(f"Frames dir: {self.frames_dir}")
        print(f"Video output: {self.video_path}")
        print("="*70)
    
    def render(self):
        """Run simulation and render frames"""
        print("\n1. Initializing components...")
        
        # SUMO (headless)
        sumo = SUMOInterface(self.config_file, use_gui=False)
        sumo.start()
        
        # Camera for rendering
        camera = AnnotatedCamera(
            image_size=(1920, 1080),
            view_range=150.0,
            intersection_center=sumo.intersection_pos
        )
        
        # Perception (FROZEN interface - Day 1)
        lane_mapper = LaneMapper(self.intersection_config)
        perception = SumoPerceptionAdapter(sumo, lane_mapper)
        
        # State estimation (FROZEN - Day 2)
        lane_ids = [f"{a}_in_{i}" for a in ['N', 'S', 'E', 'W'] for i in range(3)]
        state_estimator = TrafficStateEstimator(lane_ids, enable_smoothing=True)
        
        # Controller (FROZEN - Day 3)
        controller = IntegratedSignalController()
        
        print("✓ Components initialized")
        
        # Spawn emergency vehicle at 60s
        emergency_spawned = False
        emergency_spawn_time = 60.0
        
        frame_count = 0
        steps = int(self.duration * 10)  # 0.1s per step
        
        print(f"\n2. Rendering {steps} frames ({self.duration}s)...")
        start_time = time_module.time()
        
        try:
            for step in range(steps):
                # Advance simulation
                sumo.step()
                current_time = sumo.get_current_time()
                
                # Spawn emergency vehicle
                if not emergency_spawned and current_time >= emergency_spawn_time:
                    print(f"\n🚨 Spawning emergency vehicle at t={current_time:.1f}s")
                    sumo.add_emergency_vehicle(route_id="N_S", vtype="ambulance")
                    emergency_spawned = True
                
                # === PERCEPTION (for controller) ===
                # Use frozen perception interface: .perceive(timestamp)
                perceived_vehicles = perception.perceive(current_time)
                
                # === STATE ESTIMATION ===
                intersection_state = state_estimator.update(perceived_vehicles, current_time)
                
                # === CONTROL ===
                # Controller returns SUMO signal state string (12 chars)
                signal_state = controller.update(intersection_state, current_time)
                
                # Apply signal to SUMO
                sumo.set_traffic_light_state(signal_state)
                
                # === RENDERING (separate from perception) ===
                # Get raw SUMO vehicles for rendering (VehicleInfo objects)
                sumo_vehicles = sumo.get_all_vehicles()
                
                # Get controller status for annotations
                status = controller.get_status()
                
                # Prepare stats for overlay
                stats = {
                    'vehicles': intersection_state.total_vehicles,
                    'stopped': intersection_state.total_stopped
                }
                
                if status['emergency_distance']:
                    stats['emergency_distance'] = status['emergency_distance']
                
                # Save annotated frame (single write per timestep)
                frame_filename = self.frames_dir / f"frame_{frame_count:06d}.png"
                camera.save_annotated_frame(
                    vehicles=sumo_vehicles,
                    signal_state=signal_state,
                    controller_mode=status['mode'],
                    current_time=current_time,
                    stats=stats,
                    filename=str(frame_filename)
                )
                
                frame_count += 1
                
                # Progress indicator
                if step % 100 == 0:
                    progress = (step / steps) * 100
                    elapsed = time_module.time() - start_time
                    eta = (elapsed / (step + 1)) * (steps - step)
                    print(f"  Progress: {progress:5.1f}% | "
                          f"Frame: {frame_count:5d} | "
                          f"Time: {current_time:5.1f}s | "
                          f"ETA: {eta:4.0f}s")
            
            elapsed_total = time_module.time() - start_time
            print(f"\n✓ Rendered {frame_count} frames in {elapsed_total:.1f}s")
            print(f"  Average: {elapsed_total/frame_count:.3f}s per frame")
            
        finally:
            sumo.close()
        
        # Create video
        self._create_video(frame_count)
    
    def _create_video(self, frame_count: int):
        """Create MP4 video from frames using ffmpeg"""
        print(f"\n3. Creating video...")
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("✗ ffmpeg not found. Install with: brew install ffmpeg")
            print(f"  Frames saved to: {self.frames_dir}")
            return
        
        # ffmpeg command
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-framerate', '10',  # 10 fps (0.1s per frame)
            '-i', str(self.frames_dir / 'frame_%06d.png'),
            '-c:v', 'libx264',  # H.264 codec
            '-preset', 'medium',
            '-crf', '23',  # Quality
            '-pix_fmt', 'yuv420p',  # QuickTime compatible
            '-movflags', '+faststart',  # Enable streaming
            str(self.video_path)
        ]
        
        print(f"  Running ffmpeg...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Check file size
            size_mb = self.video_path.stat().st_size / (1024 * 1024)
            
            print(f"\n✓ Video created successfully!")
            print(f"  Path: {self.video_path}")
            print(f"  Size: {size_mb:.1f} MB")
            print(f"  Duration: {self.duration}s @ 10 fps")
            print(f"  Frames: {frame_count}")
            
        except subprocess.CalledProcessError as e:
            print(f"✗ ffmpeg failed:")
            print(e.stderr)
    
    def cleanup_frames(self):
        """Optional: Delete frames after video creation"""
        print(f"\n4. Cleaning up frames...")
        import shutil
        if self.frames_dir.exists():
            shutil.rmtree(self.frames_dir)
            print(f"✓ Deleted {self.frames_dir}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Render SUMO traffic simulation with Adaptive+Emergency controller'
    )
    parser.add_argument('--duration', type=float, default=120.0,
                       help='Simulation duration in seconds (default: 120)')
    parser.add_argument('--cleanup', action='store_true',
                       help='Delete frames after creating video')
    
    args = parser.parse_args()
    
    renderer = SimulationRenderer(duration=args.duration)
    renderer.render()
    
    if args.cleanup:
        renderer.cleanup_frames()
    
    print("\n" + "="*70)
    print("✓ RENDERING COMPLETE")
    print("="*70)
    print(f"\nTo play video:")
    print(f"  open {renderer.video_path}")


if __name__ == "__main__":
    main()
