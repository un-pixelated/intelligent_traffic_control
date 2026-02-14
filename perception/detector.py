"""
YOLOv8-based vehicle detector.
Detects vehicles, trucks, and emergency vehicles from camera frames.
"""

import numpy as np
from ultralytics import YOLO
from typing import List, Tuple, Dict
from dataclasses import dataclass
import torch


@dataclass
class Detection:
    """Single detection from YOLOv8"""
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str


class VehicleDetector:
    """
    YOLOv8-based vehicle detector.
    Uses pretrained COCO model for vehicle detection.
    """
    
    def __init__(self, model_name: str = 'yolov8n.pt', device: str = 'mps'):
        """
        Initialize detector
        
        Args:
            model_name: YOLOv8 model variant ('yolov8n.pt', 'yolov8s.pt', etc.)
            device: Device to run on ('mps' for M4 Mac, 'cuda' for GPU, 'cpu')
        """
        # Check device availability
        if device == 'mps' and not torch.backends.mps.is_available():
            print("⚠ MPS not available, falling back to CPU")
            device = 'cpu'
        elif device == 'cuda' and not torch.cuda.is_available():
            print("⚠ CUDA not available, falling back to CPU")
            device = 'cpu'
        
        self.device = device
        print(f"Loading YOLOv8 model on {device}...")
        
        # Load YOLO model
        self.model = YOLO(model_name)
        self.model.to(device)
        
        # COCO classes for vehicles
        # 2: car, 3: motorcycle, 5: bus, 7: truck
        self.vehicle_classes = {2, 3, 5, 7}
        self.class_names = {
            2: 'car',
            3: 'motorcycle', 
            5: 'bus',
            7: 'truck'
        }
        
        print(f"✓ YOLOv8 loaded successfully")
    
    def detect(self, frame: np.ndarray, conf_threshold: float = 0.3) -> List[Detection]:
        """
        Detect vehicles in frame
        
        Args:
            frame: RGB image (H, W, 3)
            conf_threshold: Confidence threshold for detections
            
        Returns:
            List of Detection objects
        """
        # Run inference
        results = self.model(frame, conf=conf_threshold, verbose=False)[0]
        
        detections = []
        
        # Parse results
        if results.boxes is not None:
            boxes = results.boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2
            confidences = results.boxes.conf.cpu().numpy()
            class_ids = results.boxes.cls.cpu().numpy().astype(int)
            
            for bbox, conf, cls_id in zip(boxes, confidences, class_ids):
                # Filter for vehicle classes
                if cls_id in self.vehicle_classes:
                    detection = Detection(
                        bbox=tuple(bbox),
                        confidence=float(conf),
                        class_id=int(cls_id),
                        class_name=self.class_names.get(cls_id, 'vehicle')
                    )
                    detections.append(detection)
        
        return detections
    
    def detect_batch(self, frames: List[np.ndarray], 
                    conf_threshold: float = 0.3) -> List[List[Detection]]:
        """
        Detect vehicles in batch of frames
        
        Args:
            frames: List of RGB images
            conf_threshold: Confidence threshold
            
        Returns:
            List of detection lists (one per frame)
        """
        results_batch = self.model(frames, conf=conf_threshold, verbose=False)
        
        all_detections = []
        for results in results_batch:
            detections = []
            if results.boxes is not None:
                boxes = results.boxes.xyxy.cpu().numpy()
                confidences = results.boxes.conf.cpu().numpy()
                class_ids = results.boxes.cls.cpu().numpy().astype(int)
                
                for bbox, conf, cls_id in zip(boxes, confidences, class_ids):
                    if cls_id in self.vehicle_classes:
                        detection = Detection(
                            bbox=tuple(bbox),
                            confidence=float(conf),
                            class_id=int(cls_id),
                            class_name=self.class_names.get(cls_id, 'vehicle')
                        )
                        detections.append(detection)
            
            all_detections.append(detections)
        
        return all_detections
    
    def visualize(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """
        Draw detections on frame
        
        Args:
            frame: RGB image
            detections: List of detections
            
        Returns:
            Annotated frame
        """
        import cv2
        
        frame_vis = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            
            # Draw bounding box
            color = (0, 255, 0)
            cv2.rectangle(frame_vis, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{det.class_name} {det.confidence:.2f}"
            cv2.putText(frame_vis, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return frame_vis
