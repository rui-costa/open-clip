"""YouTube Uploader Command-Line Interface"""

import sys
from pathlib import Path

# Ensure the root directory is in sys.path so we can import 'backend'
root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

import argparse
import logging
from backend.src.orchestrator import PipelineOrchestrator
from backend.src.manager import ProjectManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _run_step(project_id, step_name):
    orchestrator = PipelineOrchestrator()
    orchestrator.run_step(project_id, step_name)

def handle_run(args):
    orchestrator = PipelineOrchestrator()
    orchestrator.run_pipeline(args.project_id)

def handle_transcribe(args):
    _run_step(args.project_id, "transcribe")

def handle_highlights(args):
    _run_step(args.project_id, "highlights")

def handle_metadata(args):
    _run_step(args.project_id, "metadata")

def handle_clipper(args):
    _run_step(args.project_id, "clipper")

def handle_upload(args):
    _run_step(args.project_id, "upload")

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

def main():
    parser = argparse.ArgumentParser(description="YouTube Uploader Command-Line Interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create
    create_parser = subparsers.add_parser("create", help="Create a project")
    create_parser.add_argument("file_path", help="Path to source file")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete a project")
    delete_parser.add_argument("project_id", help="Project ID")

    # Run full pipeline
    run_parser = subparsers.add_parser("run", help="Run the full pipeline")
    run_parser.add_argument("project_id", help="Project ID")

    # Transcribe (Requires project_id)
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe project source")
    transcribe_parser.add_argument("project_id", help="Project ID")

    # Highlights (Requires project_id)
    highlights_parser = subparsers.add_parser("highlights", help="Extract project highlights")
    highlights_parser.add_argument("project_id", help="Project ID")

    # Metadata (Requires project_id)
    metadata_parser = subparsers.add_parser("metadata", help="Generate project metadata")
    metadata_parser.add_argument("project_id", help="Project ID")

    # Clipper (Requires project_id)
    clipper_parser = subparsers.add_parser("clipper", help="Generate video clips")
    clipper_parser.add_argument("project_id", help="Project ID")

    # Upload (Requires project_id)
    upload_parser = subparsers.add_parser("upload", help="Upload clips")
    upload_parser.add_argument("project_id", help="Project ID")

    args = parser.parse_args()

    if args.command == "create":
        handle_create(args)
    elif args.command == "run":
        handle_run(args)
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
