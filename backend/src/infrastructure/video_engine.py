from typing import Tuple, Optional, Any
from abc import ABC, abstractmethod
import cv2

class VideoEngine(ABC):
    @abstractmethod
    def get_subject_center(self, input_path: str, timestamp: float) -> Optional[Tuple[float, float]]:
        pass

    @abstractmethod
    def process_clip(self, input_path: str, output_path: str, start: float, end: float, aspect_ratio: str, resolution: str) -> None:
        pass

class Viewport:
    def __init__(self, src_w, src_h, target_w, target_h):
        self.scale = max(target_w / src_w, target_h / src_h)
        self.scaled_w = src_w * self.scale
        self.scaled_h = src_h * self.scale
        self.target_w = target_w
        self.target_h = target_h

    def get_crop_coords(self, subject_x=0.5, subject_y=0.5):
        sx, sy = subject_x * self.scaled_w, subject_y * self.scaled_h
        x1 = max(0, min(sx - (self.target_w / 2), self.scaled_w - self.target_w))
        y1 = max(0, min(sy - (self.target_h / 2), self.scaled_h - self.target_h))
        return x1, y1

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
            # YOLO xywh is [center_x, center_y, width, height]
            return (float(box[0]) / w, float(box[1]) / h)
        return None

    def process_clip(self, input_path: str, output_path: str, start: float, end: float, aspect_ratio: str, resolution: str) -> None:
        from moviepy import VideoFileClip
        from moviepy.video.fx import Crop
        import json
        
        with open("backend/config/resolutions.json", "r") as f:
            res_map = json.load(f)
        with open("backend/config/aspect_ratios.json", "r") as f:
            ar_map = json.load(f)
        
        with VideoFileClip(input_path) as video:
            clip = video.subclipped(start, end)
            
            # Resolve Dimensions
            if aspect_ratio == "keep-original":
                ar_ratio = clip.w / clip.h
            else:
                ar_val = ar_map.get(aspect_ratio, aspect_ratio)
                ar_w, ar_h = map(int, ar_val.split(':'))
                ar_ratio = ar_w / ar_h
            
            if resolution == "keep-original":
                target_w, target_h = clip.w, clip.h
            else:
                target_res = res_map.get(resolution, resolution)
                target_w, target_h = map(int, target_res.split('x'))
            
            # If resolution keep-original but AR changed, adjust target dims
            if resolution == "keep-original" and aspect_ratio != "keep-original":
                if (ar_ratio < 1) != (clip.w / clip.h < 1):
                    target_w, target_h = clip.h, clip.w
                target_w = int(target_h * ar_ratio)
            elif aspect_ratio != "keep-original":
                # Ensure resolution matches AR if AR is provided
                if abs((target_w / target_h) - ar_ratio) > 0.01:
                    if target_w / target_h > ar_ratio:
                        target_w = int(target_h * ar_ratio)
                    else:
                        target_h = int(target_w / ar_ratio)

            # Viewport Math
            vp = Viewport(clip.w, clip.h, target_w, target_h)
            clip = clip.resized(vp.scale)
            
            # Smart Center
            subj = self.get_subject_center(input_path, start) or (0.5, 0.5)
            x1, y1 = vp.get_crop_coords(subj[0], subj[1])
            
            final_clip = Crop(x1=x1, y1=y1, width=target_w, height=target_h).apply(clip)
            final_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
