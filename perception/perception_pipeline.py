"""
Complete perception pipeline integrating detection, tracking, and lane mapping.
Produces structured vehicle information for control system.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
import cv2

from perception.types import PerceivedVehicle
from perception.emergency_detection import EmergencyVehicleDetector
from perception.detector import VehicleDetector
from perception.tracker import ByteTracker, Track
from perception.lane_mapper import LaneMapper
from perception.distance_estimator import KalmanDistanceEstimator


class PerceptionPipeline:
    """
    Complete perception pipeline.
    Frame → Detections → Tracks → Lane Assignment → Structured Output
    """
    
    def __init__(self,
                 config_path: str,
                 camera_scale: float,
                 intersection_center: Tuple[float, float],
                 model_name: str = 'yolov8n.pt',
                 device: str = 'mps'):
        """
        Initialize perception pipeline
        
        Args:
            config_path: Path to intersection_config.yaml
            camera_scale: Pixels per meter from camera
            intersection_center: Center of intersection in world coords
            model_name: YOLOv8 model
            device: Computing device
        """
        print("Initializing Perception Pipeline...")
        
        # Initialize components
        self.detector = VehicleDetector(model_name=model_name, device=device)
        self.tracker = ByteTracker(track_thresh=0.5, track_buffer=30, match_thresh=0.8)
        self.lane_mapper = LaneMapper(config_path)
        self.distance_estimator = KalmanDistanceEstimator(dt=0.1)
        
        # Camera parameters
        self.camera_scale = camera_scale
        self.intersection_center = intersection_center
        
        print("✓ Perception pipeline ready")
    
    def process_frame(self, frame: np.ndarray, 
                     image_center: Tuple[int, int]) -> List[PerceivedVehicle]:
        """
        Process single frame through complete pipeline
        
        Args:
            frame: RGB image
            image_center: Center of image (pixels)
            
        Returns:
            List of perceived vehicles with complete information
        """
        # 1. Detect vehicles
        detections = self.detector.detect(frame, conf_threshold=0.3)
        
        # 2. Track vehicles
        tracks = self.tracker.update(detections)
        
        # 3. Process each track
        perceived_vehicles = []
        for track in tracks:
            # Convert bbox center to world coordinates
            world_pos = self._image_to_world(track.bbox, image_center)
            
            # Estimate velocity in world coordinates
            world_vel = self._velocity_to_world(track.velocity)
            
            # Update Kalman filter
            smoothed_x, smoothed_y, smooth_vx, smooth_vy = \
                self.distance_estimator.update(track.track_id, world_pos)
            
            # Assign to lane
            lane_id = self.lane_mapper.assign_lane((smoothed_x, smoothed_y))
            
            # Calculate distance to stop line
            if lane_id:
                dist_to_stop = self.lane_mapper.get_distance_to_stop_line(
                    (smoothed_x, smoothed_y), lane_id
                )
            else:
                dist_to_stop = -1.0
            
            # Check if emergency vehicle
            is_emergency = EmergencyVehicleDetector.is_emergency_vision(
                track.class_name
            )
            
            # Create perceived vehicle
            vehicle = PerceivedVehicle(
                track_id=track.track_id,
                bbox=track.bbox,
                class_name=track.class_name,
                position=(smoothed_x, smoothed_y),
                velocity=(smooth_vx, smooth_vy),
                lane_id=lane_id,
                distance_to_stop_line=dist_to_stop,
                is_emergency=is_emergency,
                confidence=track.confidence
            )
            perceived_vehicles.append(vehicle)
        
        return perceived_vehicles
    
    def _image_to_world(self, bbox: Tuple[float, float, float, float],
                       image_center: Tuple[int, int]) -> Tuple[float, float]:
        """Convert bounding box center from image to world coordinates"""
        x1, y1, x2, y2 = bbox
        
        # Bbox center in image coordinates
        img_x = (x1 + x2) / 2
        img_y = (y1 + y2) / 2
        
        # Convert to world coordinates
        # Image: (0,0) at top-left, Y increases downward
        # World: intersection center, Y increases upward
        rel_x = (img_x - image_center[0]) / self.camera_scale
        rel_y = -(img_y - image_center[1]) / self.camera_scale  # Flip Y
        
        world_x = self.intersection_center[0] + rel_x
        world_y = self.intersection_center[1] + rel_y
        
        return (world_x, world_y)
    
    def _velocity_to_world(self, velocity: Tuple[float, float]) -> Tuple[float, float]:
        """Convert pixel velocity to world velocity (m/s)"""
        # velocity is in pixels/frame, scale is pixels/meter
        # Assuming 10 FPS (0.1s per frame)
        vx_world = velocity[0] / self.camera_scale / 0.1
        vy_world = -velocity[1] / self.camera_scale / 0.1  # Flip Y
        
        return (vx_world, vy_world)
    
    def visualize(self, frame: np.ndarray, 
                 vehicles: List[PerceivedVehicle]) -> np.ndarray:
        """Draw perception results on frame"""
        frame_vis = frame.copy()
        
        for vehicle in vehicles:
            x1, y1, x2, y2 = [int(v) for v in vehicle.bbox]
            
            # Color based on vehicle type
            if vehicle.is_emergency:
                color = (255, 0, 0)  # Red
            elif vehicle.lane_id:
                color = (0, 255, 0)  # Green (in lane)
            else:
                color = (128, 128, 128)  # Gray (no lane)
            
            # Draw bbox
            cv2.rectangle(frame_vis, (x1, y1), (x2, y2), color, 2)
            
            # Draw info
            info_lines = [
                f"ID:{vehicle.track_id}",
                f"{vehicle.class_name}",
            ]
            if vehicle.lane_id:
                info_lines.append(f"Lane:{vehicle.lane_id}")
                info_lines.append(f"Dist:{vehicle.distance_to_stop_line:.1f}m")
            
            y_offset = y1 - 10
            for line in info_lines:
                cv2.putText(frame_vis, line, (x1, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                y_offset -= 15
        
        return frame_vis
    
    def reset(self):
        """Reset pipeline state"""
        self.tracker.reset()
        self.distance_estimator.reset()
