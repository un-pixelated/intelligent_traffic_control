"""
Virtual camera rendering from SUMO simulation.
Converts vehicle positions to image coordinates for perception models.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Dict
import cv2

from simulation.sumo_interface import VehicleInfo


class VirtualCamera:
    """
    Renders top-down view of intersection from SUMO data.
    Simulates camera feed for perception pipeline.
    """
    
    def __init__(self, 
                 image_size: Tuple[int, int] = (1280, 720),
                 view_range: float = 150.0,
                 intersection_center: Tuple[float, float] = (0.0, 0.0)):
        """
        Initialize virtual camera
        
        Args:
            image_size: Output image dimensions (width, height)
            view_range: Range of view in meters from intersection center
            intersection_center: Center point in SUMO coordinates
        """
        self.image_size = image_size
        self.view_range = view_range
        self.intersection_center = intersection_center
        
        # Calculate scale (pixels per meter)
        self.scale = min(image_size) / (2 * view_range)
        
        # Vehicle rendering parameters
        self.vehicle_sizes = {
            'car': (5.0, 2.0),  # length, width in meters
            'truck': (12.0, 2.5),
            'ambulance': (6.0, 2.3),
            'fire_truck': (8.0, 2.5),
            'default': (5.0, 2.0)
        }
        
        self.vehicle_colors = {
            'car': (100, 100, 255),  # Blue
            'truck': (150, 150, 150),  # Gray
            'ambulance': (255, 0, 0),  # Red
            'fire_truck': (255, 100, 0),  # Orange-red
            'default': (200, 200, 200)
        }
    
    def world_to_image(self, x: float, y: float) -> Tuple[int, int]:
        """
        Convert SUMO world coordinates to image pixel coordinates
        
        Args:
            x, y: Position in SUMO coordinate system (meters)
        
        Returns:
            (px, py): Pixel coordinates in image
        """
        # Translate relative to intersection
        rel_x = x - self.intersection_center[0]
        rel_y = y - self.intersection_center[1]
        
        # Scale to pixels (flip Y axis for image coordinates)
        px = int(self.image_size[0] / 2 + rel_x * self.scale)
        py = int(self.image_size[1] / 2 - rel_y * self.scale)
        
        return (px, py)
    
    def render_frame(self, vehicles: List[VehicleInfo]) -> np.ndarray:
        """
        Render current simulation state as image
        
        Args:
            vehicles: List of vehicles to render
        
        Returns:
            RGB image as numpy array (H, W, 3)
        """
        # Create blank canvas
        img = Image.new('RGB', self.image_size, color=(50, 50, 50))
        draw = ImageDraw.Draw(img)
        
        # Draw road structure
        self._draw_roads(draw)
        
        # Draw each vehicle
        for vehicle in vehicles:
            self._draw_vehicle(draw, vehicle)
        
        # Convert to numpy array
        return np.array(img)
    
    def _draw_roads(self, draw: ImageDraw.Draw):
        """Draw road lanes and intersection"""
        road_color = (80, 80, 80)
        lane_color = (200, 200, 200)
        
        # Draw main roads (4 directions)
        road_width_meters = 10.0  # 3 lanes * ~3.3m each
        road_width_px = int(road_width_meters * self.scale)
        
        center_px = (self.image_size[0] // 2, self.image_size[1] // 2)
        
        # North-South road
        draw.rectangle([
            center_px[0] - road_width_px // 2, 0,
            center_px[0] + road_width_px // 2, self.image_size[1]
        ], fill=road_color)
        
        # East-West road
        draw.rectangle([
            0, center_px[1] - road_width_px // 2,
            self.image_size[0], center_px[1] + road_width_px // 2
        ], fill=road_color)
        
        # Draw lane markings (dashed lines)
        lane_width_px = int(3.3 * self.scale)
        
        # Vertical lanes
        for i in range(-1, 2):
            x = center_px[0] + i * lane_width_px
            for y in range(0, self.image_size[1], 20):
                draw.line([(x, y), (x, y + 10)], fill=lane_color, width=2)
        
        # Horizontal lanes
        for i in range(-1, 2):
            y = center_px[1] + i * lane_width_px
            for x in range(0, self.image_size[0], 20):
                draw.line([(x, y), (x + 10, y)], fill=lane_color, width=2)
        
        # Draw stop lines
        stop_line_color = (255, 255, 255)
        stop_distance_meters = 5.0
        stop_distance_px = int(stop_distance_meters * self.scale)
        
        # North stop line
        draw.line([
            (center_px[0] - road_width_px // 2, center_px[1] - stop_distance_px),
            (center_px[0] + road_width_px // 2, center_px[1] - stop_distance_px)
        ], fill=stop_line_color, width=3)
        
        # South stop line
        draw.line([
            (center_px[0] - road_width_px // 2, center_px[1] + stop_distance_px),
            (center_px[0] + road_width_px // 2, center_px[1] + stop_distance_px)
        ], fill=stop_line_color, width=3)
        
        # East stop line
        draw.line([
            (center_px[0] + stop_distance_px, center_px[1] - road_width_px // 2),
            (center_px[0] + stop_distance_px, center_px[1] + road_width_px // 2)
        ], fill=stop_line_color, width=3)
        
        # West stop line
        draw.line([
            (center_px[0] - stop_distance_px, center_px[1] - road_width_px // 2),
            (center_px[0] - stop_distance_px, center_px[1] + road_width_px // 2)
        ], fill=stop_line_color, width=3)
    
    def _draw_vehicle(self, draw: ImageDraw.Draw, vehicle: VehicleInfo):
        """Draw a single vehicle"""
        # Get vehicle dimensions
        length, width = self.vehicle_sizes.get(
            vehicle.type, 
            self.vehicle_sizes['default']
        )
        
        # Get color
        color = self.vehicle_colors.get(
            vehicle.type,
            self.vehicle_colors['default']
        )
        
        # Convert to pixels
        length_px = length * self.scale
        width_px = width * self.scale
        
        # Get position
        center_px = self.world_to_image(vehicle.position[0], vehicle.position[1])
        
        # Create rotated rectangle
        angle_rad = np.radians(vehicle.angle - 90)  # Adjust for SUMO's angle convention
        
        # Calculate corner offsets
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        half_l = length_px / 2
        half_w = width_px / 2
        
        corners = [
            (-half_l, -half_w),
            (half_l, -half_w),
            (half_l, half_w),
            (-half_l, half_w)
        ]
        
        # Rotate and translate corners
        rotated_corners = []
        for dx, dy in corners:
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a
            rotated_corners.append((
                int(center_px[0] + rx),
                int(center_px[1] + ry)
            ))
        
        # Draw vehicle
        draw.polygon(rotated_corners, fill=color, outline=(255, 255, 255))
        
        # Draw directional indicator (front of vehicle)
        front_x = center_px[0] + half_l * cos_a
        front_y = center_px[1] + half_l * sin_a
        draw.ellipse([
            front_x - 3, front_y - 3,
            front_x + 3, front_y + 3
        ], fill=(255, 255, 0))
    
    def save_frame(self, vehicles: List[VehicleInfo], filename: str):
        """Render and save frame to file"""
        frame = self.render_frame(vehicles)
        cv2.imwrite(filename, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))