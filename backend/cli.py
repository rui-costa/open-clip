"""YouTube Uploader Command-Line Interface"""

import sys
from pathlib import Path

# Ensure the root directory is in sys.path so we can import 'backend'
root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

import argparse
import logging
import json
import asyncio
import csv

from backend.src.uploader import YoutubeUploader
from backend.src.manager import ProjectManager
from backend.src.transcriber import Transcriber
from backend.src.llm_executor import LLMTaskExecutor
from backend.src.clipper import Clipper, SubjectTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_clipper(args):
    manager = ProjectManager()
    metadata = manager.get_metadata(args.project_id)
    project_path = manager.get_project_path(args.project_id)
    clips_dir = project_path / "clips"
    clips_dir.mkdir(exist_ok=True)
    
    # Initialize clips to empty to start fresh
    metadata.clips = []
    metadata.clipper_start = None
    metadata.clipper_end = None
    
    # Use highlights from metadata instead of a separate file
    highlights_data = metadata.highlights
    metadata.components["total_expected_clips"] = len(highlights_data)
    
    manager.save_project_metadata(args.project_id, metadata)
    
    # Ensure absolute path is used for the clipper
    input_video_path = str(project_path / metadata.original_file)
    
    clipper = Clipper(
        input_path=input_video_path,
        output_dir=str(clips_dir),
        project_root=str(project_path.parent.parent / "root"),
        aspect_ratio=metadata.settings.aspect_ratio,
        resolution=metadata.settings.resolution
    )
    
    if args.clip_index is not None:
        print("Note: --clip-index is currently handled by re-filtering the highlights list.")
    
    clips_metadata, clipper_start, clipper_end = clipper.cut_clips(
        highlights=metadata.highlights,
        manager=manager,
        project_id=args.project_id
    )
    
    # Final update after all clips are generated
    metadata.clips = clips_metadata
    metadata.clipper_start = clipper_start
    metadata.clipper_end = clipper_end
    metadata.components["clips_dir"] = str(clips_dir)
    manager.save_project_metadata(args.project_id, metadata)
    print(f"Clips generated in {clips_dir} for project {args.project_id}")

def handle_create(args):
    manager = ProjectManager()
    path = manager.create_project(file_path=args.file_path)
    print(path.name)

def handle_delete(args):
    manager = ProjectManager()
    if manager.delete_project(args.project_id):
        print(f"Project {args.project_id} deleted.")
    else:
        print(f"Error: Project {args.project_id} not found.")

def handle_transcribe(args):
    manager = ProjectManager() 
    project_path = manager.get_project_path(args.project_id)
    metadata = manager.get_metadata(args.project_id)
    source_file = metadata.original_file
    
    if not source_file:
        print(f"Error: No source file defined for project {args.project_id}")
        return

    transcriber = Transcriber(model=args.model)
    # Pass the project path to resolve relative source_file paths
    result = transcriber.transcribe(source_file, project_path=str(project_path), language=args.language)
    
    # Save files to project directory
    output_file1 = project_path / "transcription.txt"
    output_file2 = project_path / "word_map.csv"
    
    with open(output_file1, "w", encoding="utf-8") as f:
        f.write(result[0])

    with open(output_file2, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "start", "end"])
        writer.writerows(result[1])
    
    # Update metadata
    metadata.transcription_file = str(output_file1)
    # Assuming word_map is a component
    metadata.components["word_map_file"] = str(output_file2)
    manager.save_project_metadata(args.project_id, metadata)
    
    print(f"Transcription saved for project {args.project_id}")

def handle_highlights(args):
    manager = ProjectManager()
    metadata = manager.get_metadata(args.project_id)
    
    async def run():
        executor = LLMTaskExecutor()
        # Use paths saved in metadata
        highlights = await executor.extract_highlights(
            transcription_text_path=metadata.transcription_file,
            word_map_csv_path=metadata.components["word_map_file"]
        )
        manager.save_highlights(args.project_id, {"highlights": highlights})
        print(f"Highlights saved for project {args.project_id}")

    asyncio.run(run())

def handle_metadata(args):
    manager = ProjectManager()
    metadata = manager.get_metadata(args.project_id)
    
    async def run():
        executor = LLMTaskExecutor()
        # Use paths saved in metadata
        result = await executor.generate_video_metadata(
            transcription_text_path=metadata.transcription_file
        )
        manager.save_task_result(args.project_id, "VIDEO_META.md", result)
        print(f"Video metadata saved for project {args.project_id}")

    asyncio.run(run())

def handle_upload(args):
    from backend.src.settings_manager import settings_manager
    project_path = Path("projects") / args.project_id
    if not project_path.exists():
        sys.stderr.write(f"Error: Project not found: {args.project_id}\n")
        sys.exit(1)

    metadata_file = project_path / "metadata.json"
    with open(metadata_file, "r") as f:
        metadata = json.load(f)

    highlights_file = project_path / "highlights.json"
    if not highlights_file.exists():
        sys.stderr.write(f"Error: Highlights file not found. Run highlights extraction first.\n")
        sys.exit(1)

    with open(highlights_file, "r") as f:
        highlights_data = json.load(f)
        highlights = highlights_data.get("highlights", [])

    client_secrets_config = settings_manager.get("youtube_client_secrets")
    if not client_secrets_config:
        sys.stderr.write(f"Error: YouTube client secrets not found in settings.\n")
        sys.exit(1)
        
    uploader = YoutubeUploader(
        credentials_dir=args.credentials_dir, 
        client_secrets_config=client_secrets_config
    )
    clips_dir = metadata.get("components", {}).get("clips_dir")
    
    if not clips_dir:
        sys.stderr.write(f"Error: No clips directory found in project. Please run clipper first.\n")
        sys.exit(1)
    
    i = 0
    for highlight in highlights:
        clip_filename = f"clip_{i:03d}.mp4"
        clip_path = Path(clips_dir) / clip_filename
        
        if not clip_path.exists():
            logger.warning(f"Clip file not found: {clip_path}, skipping.")
            continue

        logger.info(f"Uploading: {highlight['video_title_for_youtube_short']}")
        result = uploader.upload_video(
            file_path=str(clip_path),
            title=highlight['video_title_for_youtube_short'],
            description=highlight['highlight_text'],
            tags=highlight.get('tags', []),
            privacy_status=args.privacy,
        )

        if "components" not in metadata:
            metadata["components"] = {}
        if "uploads" not in metadata["components"]:
            metadata["components"]["uploads"] = []

        upload_record = {
            "clip_id": i,
            "youtube_video_id": result["video_id"],
            "title": highlight['highlight_text'],
        }
        metadata["components"]["uploads"].append(upload_record)

        i += 1
        
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Process complete.")

def main():
    parser = argparse.ArgumentParser(description="YouTube Uploader Command-Line Interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create
    create_parser = subparsers.add_parser("create", help="Create a project")
    create_parser.add_argument("file_path", help="Path to source file")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete a project")
    delete_parser.add_argument("project_id", help="Project ID")

    # Transcribe (Requires project_id)
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe project source")
    transcribe_parser.add_argument("project_id", help="Project ID")
    transcribe_parser.add_argument("--model", default="base", help="Whisper model to use")
    transcribe_parser.add_argument("--language", help="Optional language code (e.g., 'en', 'pt')")

    # Highlights (Requires project_id)
    highlights_parser = subparsers.add_parser("highlights", help="Extract project highlights")
    highlights_parser.add_argument("project_id", help="Project ID")

    # Metadata (Requires project_id)
    metadata_parser = subparsers.add_parser("metadata", help="Generate project metadata")
    metadata_parser.add_argument("project_id", help="Project ID")

    # Clipper (Requires project_id)
    clipper_parser = subparsers.add_parser("clipper", help="Generate video clips")
    clipper_parser.add_argument("project_id", help="Project ID")
    clipper_parser.add_argument("--clip-index", type=int, help="Optional: Index of a single clip to render")

    # Upload (Requires project_id)
    upload_parser = subparsers.add_parser("upload", help="Upload clips")
    upload_parser.add_argument("project_id", help="Project ID")
    upload_parser.add_argument("--privacy", default="private", choices=["private", "public", "unlisted"])
    upload_parser.add_argument("--credentials-dir", default="./backend/youtube_credentials", help="Credentials dir")

    args = parser.parse_args()

    if args.command == "create":
        handle_create(args)
    elif args.command == "delete":
        handle_delete(args)
    elif args.command == "transcribe":
        handle_transcribe(args)
    elif args.command == "highlights":
        handle_highlights(args)
    elif args.command == "metadata":
        handle_metadata(args)
    elif args.command == "clipper":
        handle_clipper(args)
    elif args.command == "upload":
        handle_upload(args)

if __name__ == "__main__":
    main()
