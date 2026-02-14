"""
ByteTrack object tracker.
Associates detections across frames to track vehicles.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import lap  # Linear assignment


@dataclass  
class Track:
    """Single tracked object"""
    track_id: int
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_name: str
    age: int  # Frames since first detection
    hits: int  # Number of successful associations
    time_since_update: int  # Frames since last update
    velocity: Tuple[float, float] = (0.0, 0.0)  # dx, dy per frame


class ByteTracker:
    """
    ByteTrack - Simple and effective multi-object tracker.
    Tracks objects using bounding box IoU matching.
    """
    
    def __init__(self, 
                 track_thresh: float = 0.5,
                 track_buffer: int = 30,
                 match_thresh: float = 0.8):
        """
        Initialize tracker
        
        Args:
            track_thresh: Detection confidence threshold for track initialization
            track_buffer: Frames to keep lost tracks before deletion
            match_thresh: IoU threshold for matching
        """
        self.track_thresh = track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        
        self.tracked_tracks: List[Track] = []
        self.lost_tracks: List[Track] = []
        self.removed_tracks: List[Track] = []
        
        self.frame_id = 0
        self.track_id_count = 0
    
    def update(self, detections: List) -> List[Track]:
        """
        Update tracker with new detections
        
        Args:
            detections: List of Detection objects from detector
            
        Returns:
            List of active tracks
        """
        self.frame_id += 1
        
        # Split detections by confidence
        high_conf_dets = [d for d in detections if d.confidence >= self.track_thresh]
        low_conf_dets = [d for d in detections if d.confidence < self.track_thresh]
        
        # Predict existing tracks
        for track in self.tracked_tracks:
            track.time_since_update += 1
        
        # First association with high confidence detections
        matches, unmatched_tracks, unmatched_dets = self._associate(
            self.tracked_tracks, high_conf_dets, self.match_thresh
        )
        
        # Update matched tracks
        for track_idx, det_idx in matches:
            track = self.tracked_tracks[track_idx]
            det = high_conf_dets[det_idx]
            self._update_track(track, det)
        
        # Second association with low confidence detections
        if len(unmatched_tracks) > 0 and len(low_conf_dets) > 0:
            unmatched_track_objs = [self.tracked_tracks[i] for i in unmatched_tracks]
            matches_low, unmatched_tracks_low, _ = self._associate(
                unmatched_track_objs, low_conf_dets, 0.5
            )
            
            for track_idx, det_idx in matches_low:
                track = unmatched_track_objs[track_idx]
                det = low_conf_dets[det_idx]
                self._update_track(track, det)
            
            unmatched_tracks = [unmatched_tracks[i] for i in unmatched_tracks_low]
        
        # Initialize new tracks from unmatched high-confidence detections
        for det_idx in unmatched_dets:
            det = high_conf_dets[det_idx]
            new_track = self._init_track(det)
            self.tracked_tracks.append(new_track)
        
        # Move unmatched tracks to lost
        for track_idx in unmatched_tracks:
            track = self.tracked_tracks[track_idx]
            self.lost_tracks.append(track)
        
        # Remove lost tracks exceeding buffer
        self.tracked_tracks = [t for i, t in enumerate(self.tracked_tracks) 
                             if i not in unmatched_tracks]
        
        # Remove old lost tracks
        self.lost_tracks = [t for t in self.lost_tracks 
                          if t.time_since_update < self.track_buffer]
        
        # Return active tracks
        active_tracks = [t for t in self.tracked_tracks if t.hits >= 2]
        return active_tracks
    
    def _associate(self, tracks: List[Track], detections: List, 
                  thresh: float) -> Tuple[List, List, List]:
        """
        Associate tracks with detections using IoU
        
        Returns:
            matches: List of (track_idx, det_idx) pairs
            unmatched_tracks: List of track indices
            unmatched_dets: List of detection indices
        """
        if len(tracks) == 0 or len(detections) == 0:
            return [], list(range(len(tracks))), list(range(len(detections)))
        
        # Compute IoU matrix
        iou_matrix = np.zeros((len(tracks), len(detections)))
        for t_idx, track in enumerate(tracks):
            for d_idx, det in enumerate(detections):
                iou_matrix[t_idx, d_idx] = self._iou(track.bbox, det.bbox)
        
        # Hungarian algorithm for assignment
        if iou_matrix.size > 0:
            # Use lap for linear assignment (faster than scipy)
            # Cost matrix = 1 - IoU (minimize cost = maximize IoU)
            cost_matrix = 1 - iou_matrix
            _, x, y = lap.lapjv(cost_matrix, extend_cost=True, cost_limit=1 - thresh)
            
            matches = [[ix, mx] for ix, mx in enumerate(x) if mx >= 0 and iou_matrix[ix, mx] >= thresh]
        else:
            matches = []
        
        # Find unmatched tracks and detections
        unmatched_tracks = [i for i in range(len(tracks)) 
                          if i not in [m[0] for m in matches]]
        unmatched_dets = [i for i in range(len(detections)) 
                        if i not in [m[1] for m in matches]]
        
        return matches, unmatched_tracks, unmatched_dets
    
    def _iou(self, bbox1: Tuple[float, float, float, float],
            bbox2: Tuple[float, float, float, float]) -> float:
        """Calculate IoU between two bounding boxes"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Intersection
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        
        # Union
        bbox1_area = (x1_max - x1_min) * (y1_max - y1_min)
        bbox2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = bbox1_area + bbox2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def _init_track(self, detection) -> Track:
        """Initialize new track from detection"""
        self.track_id_count += 1
        
        return Track(
            track_id=self.track_id_count,
            bbox=detection.bbox,
            confidence=detection.confidence,
            class_name=detection.class_name,
            age=1,
            hits=1,
            time_since_update=0,
            velocity=(0.0, 0.0)
        )
    
    def _update_track(self, track: Track, detection):
        """Update existing track with new detection"""
        # Calculate velocity
        old_center = self._bbox_center(track.bbox)
        new_center = self._bbox_center(detection.bbox)
        velocity = (new_center[0] - old_center[0], new_center[1] - old_center[1])
        
        # Update track
        track.bbox = detection.bbox
        track.confidence = detection.confidence
        track.age += 1
        track.hits += 1
        track.time_since_update = 0
        track.velocity = velocity
    
    def _bbox_center(self, bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
        """Get center point of bounding box"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    
    def reset(self):
        """Reset tracker state"""
        self.tracked_tracks = []
        self.lost_tracks = []
        self.removed_tracks = []
        self.frame_id = 0
        self.track_id_count = 0
