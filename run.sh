#!/bin/bash

# run.sh
# Usage: ./run.sh <video_file>

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <video_file>"
    exit 1
fi

VIDEO_FILE=$1

PROJECT_ID=$(python backend/cli.py create "${VIDEO_FILE//\\/}")
echo "Project ID: $PROJECT_ID"

python backend/cli.py transcribe $PROJECT_ID --language en
python backend/cli.py highlights $PROJECT_ID 
python backend/cli.py metadata $PROJECT_ID
python backend/cli.py clipper $PROJECT_ID
python backend/cli.py upload $PROJECT_ID
