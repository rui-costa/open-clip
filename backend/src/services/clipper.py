import os
import shutil
import pytest
from typing import List, Dict, Any, Tuple
from backend.src.project import Project
from backend.src.infrastructure.video_engine import OpenCVVideoEngine

class Clipper:
    def reset_metadata(self, project: Project) -> None:
        """Clears the clips/ directory and resets clip state."""
        clips_dir = os.path.join(os.path.dirname(str(project.files.original_file)), "clips")
        if os.path.exists(clips_dir):
            shutil.rmtree(clips_dir)
        os.makedirs(clips_dir, exist_ok=True)
        # Note: Project model updates would be handled here or by orchestrator
        project.clips = []

    def start_service(self, project: Project) -> None:
        """Initializes the service and resets metadata."""
        self.reset_metadata(project)

    def execute(self, project: Project) -> List[Dict[str, Any]]:  # pragma: no cover
        """Executes clipping logic."""
        engine = OpenCVVideoEngine("root/yolov8n.pt")
        input_path = str(project.files.original_file)
        clips_dir = os.path.join(os.path.dirname(input_path), "clips")
        
        clips_metadata = []
        for i, short in enumerate(project.highlights):
            start = max(0.0, float(short.start))
            end = float(short.end)
            filename = f"clip_{i:03d}.mp4"
            output_path = os.path.join(clips_dir, filename)
            
            engine.process_clip(
                input_path, 
                output_path, 
                start, 
                end, 
                project.settings.aspect_ratio, 
                project.settings.resolution
            )
            
            clips_metadata.append({
                "filename": filename,
                "processed_start": start,
                "processed_end": end,
                "text": short.highlight_text
            })
        
        return clips_metadata

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        pass
