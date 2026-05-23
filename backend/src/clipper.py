import json
import os
import csv
import cv2
from ultralytics import YOLO
from typing import List, Dict, Optional, Any
from moviepy import VideoFileClip
from backend.src.repository import StorageRepository
from backend.src.fs_repository import FileSystemRepository

class SubjectTracker:
    def __init__(self, input_path: str, model_path: str):
        self.input_path = input_path
        self.model = YOLO(model_path)
        self.cap = cv2.VideoCapture(self.input_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)

    def get_subject_center(self, timestamp: float) -> Optional[tuple]:
        frame_idx = int(timestamp * self.fps)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()

        if not ret:
            return None

        results = self.model(frame, classes=[0], verbose=False)
        if len(results) > 0 and len(results[0].boxes) > 0:
            box = results[0].boxes[0].xywh[0]
            return (float(box[0]), float(box[1]))
        return None

    def __del__(self):
        self.cap.release()

class Clipper:
    # Resolution tiers mapped to their "height" dimension (used as basis for scaling)
    RESOLUTION_MAP = {
        'HD': 720,
        'FHD': 1080,
        '2K': 1440,
        '4K': 2160
    }

    def __init__(self, input_path: str, output_dir: str, project_root: str, repo: Optional[StorageRepository] = None, aspect_ratio: str = '9:16', resolution: str = None):
        self.input_path = input_path
        self.output_dir = output_dir
        self.project_root = project_root
        self.repo = repo or FileSystemRepository()
        self.aspect_ratio = aspect_ratio
        self.resolution = resolution
        self.tracker = SubjectTracker(input_path, os.path.join(self.project_root, 'yolov8n.pt'))
        os.makedirs(output_dir, exist_ok=True)

    def _detect_resolution_tier(self) -> str:
        """Detect the resolution tier of the input video based on its height."""
        try:
            with VideoFileClip(self.input_path) as video:
                _, video_h = video.size
            
            # Map video height to resolution tier
            if video_h <= 720:
                return 'HD'
            elif video_h <= 1080:
                return 'FHD'
            elif video_h <= 1440:
                return '2K'
            else:
                return '4K'
        except Exception:
            # Default to FHD if detection fails
            return 'FHD'

    def _calculate_target_dimensions(self, target_height: int) -> tuple:
        """Calculate target width and height based on aspect ratio and target height."""
        if not self.aspect_ratio:
            return None
        
        w_ratio, h_ratio = map(int, self.aspect_ratio.split(':'))
        target_width = int(target_height * w_ratio / h_ratio)
        return (target_width, target_height)

    def cut_clips(self, highlights: List[Dict[str, Any]], manager: Optional[Any] = None, project_id: Optional[str] = None) -> tuple[List[Dict[str, Any]], Optional[float], Optional[float]]:
        shorts = highlights
        total_clips = len(shorts)
        
        clips_metadata = []
        all_starts = []
        all_ends = []
        
        for i, short in enumerate(shorts):
            try:
                start = float(short.get('start', 0))
                end = float(short.get('end', 0))
            except (ValueError, TypeError):
                continue
            
            if start == 0.0 and end == 0.0:
                continue
                
            start = max(0.0, start)
            filename = f"clip_{i:03d}.mp4"
            
            self.generate_single_clip(float(start), float(end), filename)
            
            clip_meta = {
                "filename": filename,
                "original_start": start,
                "original_end": end,
                "processed_start": start,
                "processed_end": end,
                "text": short.get('highlight_text', '')
            }
            clips_metadata.append(clip_meta)
            
            if manager and project_id:
                metadata = manager.get_metadata(project_id)
                metadata.clips = list(clips_metadata)
                manager.save_project_metadata(project_id, metadata)
                
            all_starts.append(start)
            all_ends.append(end)
            
        clipper_start = min(all_starts) if all_starts else None
        clipper_end = max(all_ends) if all_ends else None
        
        return clips_metadata, clipper_start, clipper_end

    def generate_single_clip(self, start: float, end: float, output_filename: str):
        with VideoFileClip(self.input_path) as video:
            clip = video.subclipped(start, end)
            
            if self.aspect_ratio:
                w_ratio, h_ratio = map(int, self.aspect_ratio.split(':'))
                target_ratio = w_ratio / h_ratio
                
                # Calculate optimal crop
                video_w, video_h = clip.size
                video_ratio = video_w / video_h
                
                if video_ratio > target_ratio:
                    new_w = int(video_h * target_ratio)
                    new_h = video_h
                    x_center = self.tracker.get_subject_center((start + end) / 2)
                    if x_center:
                        x1 = max(0, min(int(x_center[0] - new_w / 2), video_w - new_w))
                    else:
                        x1 = (video_w - new_w) // 2
                    y1 = 0
                else:
                    new_w = video_w
                    new_h = int(video_w / target_ratio)
                    x_center = self.tracker.get_subject_center((start + end) / 2)
                    x1 = 0
                    if x_center:
                        y1 = max(0, min(int(x_center[1] - new_h / 2), video_h - new_h))
                    else:
                        y1 = (video_h - new_h) // 2
                
                clip = clip.cropped(x1=x1, y1=y1, width=new_w, height=new_h)
            
            # Resize based on resolution tier while maintaining aspect ratio
            # If no resolution is specified, detect it from the original video
            resolution_tier = self.resolution or self._detect_resolution_tier()
            if resolution_tier in self.RESOLUTION_MAP:
                target_height = self.RESOLUTION_MAP[resolution_tier]
                target_dimensions = self._calculate_target_dimensions(target_height)
                if target_dimensions:
                    clip = clip.resized(new_size=target_dimensions)
            
            output_file = os.path.join(self.output_dir, output_filename)
            clip.write_videofile(output_file, codec='libx264', audio_codec='aac')
