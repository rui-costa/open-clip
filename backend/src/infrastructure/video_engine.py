import cv2
import subprocess
import shutil
import json
import logging
from typing import Tuple, Optional, Any
from abc import ABC, abstractmethod
from pathlib import Path
from backend.src.settings_manager import settings_manager

logger = logging.getLogger(__name__)

# Utility for viewport math
def calculate_crop_params(src_w, src_h, target_w, target_h, subject_x=0.5, subject_y=0.5):
    scale = max(target_w / src_w, target_h / src_h)
    scaled_w, scaled_h = src_w * scale, src_h * scale
    
    # Calculate crop coordinates
    x1 = max(0, min(subject_x * scaled_w - (target_w / 2), scaled_w - target_w))
    y1 = max(0, min(subject_y * scaled_h - (target_h / 2), scaled_h - target_h))
    
    return float(scale), int(x1), int(y1)

class VideoEngine(ABC):
    @abstractmethod
    def get_subject_center(self, input_path: str, timestamp: float) -> Optional[Tuple[float, float]]:
        pass

    @abstractmethod
    def process_clip(self, input_path: str, output_path: str, start: float, end: float, aspect_ratio: str, resolution: str) -> None:
        pass

class OpenCVVideoEngine(VideoEngine):
    def __init__(self, model_path: str):
        from ultralytics import YOLO
        self.model = YOLO(model_path)

    def get_subject_center(self, input_path: str, timestamp: float) -> Optional[Tuple[float, float]]:
        cap = cv2.VideoCapture(input_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_idx = int(timestamp * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()
        if not ret: return None
        h, w = frame.shape[:2]
        results = self.model(frame, classes=[0], verbose=False)
        if len(results) > 0 and len(results[0].boxes) > 0:
            box = results[0].boxes[0].xywh[0]
            return (float(box[0]) / w, float(box[1]) / h)
        return None

    def process_clip(self, input_path: str, output_path: str, start: float, end: float, aspect_ratio: str, resolution: str) -> None:
        with open("backend/config/resolutions.json", "r") as f:
            res_map = json.load(f)
        with open("backend/config/aspect_ratios.json", "r") as f:
            ar_map = json.load(f)

        # Get metadata for dimensions
        cap = cv2.VideoCapture(input_path)
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        # Resolve Target Dimensions
        ar_w, ar_h = map(int, aspect_ratio.split(':'))
        if resolution == "keep original":
            # Use source dimensions but apply the aspect ratio
            if ar_w / ar_h >= src_w / src_h:
                target_w, target_h = src_w, int(src_w * ar_h / ar_w)
            else:
                target_w, target_h = int(src_h * ar_w / ar_h), src_h
        else:
            target_w, target_h = map(int, res_map.get(resolution, resolution).split('x'))
        # Ensure dimensions are even (required by most codecs)
        target_w = target_w - (target_w % 2)
        target_h = target_h - (target_h % 2)

        # Smart Center
        subj_x, subj_y = self.get_subject_center(input_path, start) or (0.5, 0.5)
        
        # Crop Math
        scale, x1, y1 = calculate_crop_params(src_w, src_h, target_w, target_h, subj_x, subj_y)
        
        # FFmpeg command
        codec = settings_manager.get("codec") or "libx264"
        logger.info(f"Encoding clip with codec: {codec}")
        
        # Build filter string
        scale_w = int(src_w * scale)
        scale_h = int(src_h * scale)
        vf = f"scale={scale_w}:{scale_h},crop={target_w}:{target_h}:{x1}:{y1}"
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-to', str(end),
            '-i', input_path,
            '-vf', vf,
            '-c:v', codec,
            '-c:a', 'aac',
            output_path
        ]
        
        subprocess.run(cmd, check=True)
