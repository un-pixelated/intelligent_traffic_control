"""
Enhanced camera with signal state annotations.
Extends VirtualCamera to show traffic signals and controller mode.

Corrected Day 3.5: Fixed to use frozen perception interface
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Dict, Optional
import cv2

from simulation.camera_interface import VirtualCamera
from simulation.sumo_interface import VehicleInfo


class AnnotatedCamera(VirtualCamera):
    """
    Renders frames with signal state and controller annotations.
    """
    
    def render_annotated_frame(self, 
                               vehicles: List[VehicleInfo],
                               signal_state: str,
                               controller_mode: str,
                               current_time: float,
                               stats: Dict[str, any]) -> np.ndarray:
        """
        Render frame with annotations
        
        Args:
            vehicles: List of SUMO VehicleInfo objects
            signal_state: SUMO signal state string (12 chars)
            controller_mode: "NORMAL" or "EMERGENCY"
            current_time: Simulation time in seconds
            stats: Dictionary with traffic stats
            
        Returns:
            RGB numpy array (H, W, 3)
        """
        # Render base frame using parent class
        img = self.render_frame(vehicles)
        
        # Convert to PIL for annotations
        pil_img = Image.fromarray(img)
        draw = ImageDraw.Draw(pil_img)
        
        # Draw signal indicators
        self._draw_signal_indicators(draw, signal_state)
        
        # Draw info overlay
        self._draw_info_overlay(draw, controller_mode, current_time, stats)
        
        # Convert back to numpy
        return np.array(pil_img)
    
    def save_annotated_frame(self,
                            vehicles: List[VehicleInfo],
                            signal_state: str,
                            controller_mode: str,
                            current_time: float,
                            stats: Dict[str, any],
                            filename: str):
        """
        Render and save annotated frame to file
        
        Args:
            vehicles: SUMO vehicles
            signal_state: Signal string
            controller_mode: Mode string
            current_time: Time in seconds
            stats: Statistics dict
            filename: Output PNG path
        """
        frame_rgb = self.render_annotated_frame(
            vehicles, signal_state, controller_mode, current_time, stats
        )
        
        # Convert RGB to BGR for OpenCV
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        
        # Write single PNG
        cv2.imwrite(filename, frame_bgr)
    
    def _draw_signal_indicators(self, draw: ImageDraw.Draw, signal_state: str):
        """
        Draw traffic signal lights at each approach
        
        Signal state format (12 chars):
        - Positions 0-2: North approach (3 lanes)
        - Positions 3-5: East approach
        - Positions 6-8: South approach
        - Positions 9-11: West approach
        
        Each char: 'G' = green, 'y' = yellow, 'r' = red
        """
        center = (self.image_size[0] // 2, self.image_size[1] // 2)
        signal_radius = 15
        signal_offset = 80
        
        # Parse signal states per approach
        signals = {
            'N': signal_state[0:3],
            'E': signal_state[3:6],
            'S': signal_state[6:9],
            'W': signal_state[9:12]
        }
        
        # Position for each approach's signal
        positions = {
            'N': (center[0], center[1] - signal_offset),
            'S': (center[0], center[1] + signal_offset),
            'E': (center[0] + signal_offset, center[1]),
            'W': (center[0] - signal_offset, center[1])
        }
        
        for approach, state_str in signals.items():
            pos = positions[approach]
            
            # Determine dominant signal (majority vote)
            green_count = state_str.count('G')
            yellow_count = state_str.count('y')
            red_count = state_str.count('r')
            
            if green_count >= 2:
                color = (0, 255, 0)  # Green
            elif yellow_count >= 1:
                color = (255, 255, 0)  # Yellow
            else:
                color = (255, 0, 0)  # Red
            
            # Draw signal light
            draw.ellipse([
                pos[0] - signal_radius, pos[1] - signal_radius,
                pos[0] + signal_radius, pos[1] + signal_radius
            ], fill=color, outline=(0, 0, 0), width=3)
            
            # Draw approach label
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
            except:
                font = ImageFont.load_default()
            
            draw.text((pos[0] - 5, pos[1] - 5), approach, 
                     fill=(255, 255, 255), font=font)
    
    def _draw_info_overlay(self, draw: ImageDraw.Draw, 
                          mode: str, time: float, stats: Dict):
        """Draw information overlay at top of frame"""
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Semi-transparent background
        overlay_height = 100
        draw.rectangle([0, 0, self.image_size[0], overlay_height], 
                      fill=(0, 0, 0))
        
        # Controller mode (highlighted if emergency)
        mode_color = (255, 50, 50) if mode == "EMERGENCY" else (50, 255, 50)
        mode_text = f"MODE: {mode}" if mode == "EMERGENCY" else f"MODE: {mode}"
        draw.text((20, 10), mode_text, fill=mode_color, font=font_large)
        
        # Time
        draw.text((20, 45), f"Time: {time:.1f}s", fill=(255, 255, 255), font=font_small)
        
        # Stats
        vehicles = stats.get('vehicles', 0)
        stopped = stats.get('stopped', 0)
        draw.text((20, 70), f"Vehicles: {vehicles} | Stopped: {stopped}", 
                 fill=(255, 255, 255), font=font_small)
        
        # Emergency info if present
        if mode == "EMERGENCY" and 'emergency_distance' in stats:
            dist = stats['emergency_distance']
            draw.text((self.image_size[0] - 300, 45), 
                     f"Emergency: {dist:.0f}m to stop line",
                     fill=(255, 100, 100), font=font_small)
