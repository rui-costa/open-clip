# Open-Clip

> An automated video clipping and processing engine.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Overview

Open-Clip is an automated video processing system designed to manage and clip video projects efficiently. It provides a full-stack solution featuring a Python based backend for processing and a web based frontend for project management.

![A clip in Open-Clip: the player with its title and captions drawn over it, the writing for each platform, the description it would be published with, and the actions](images/clip_detail.png)

Upload an episode, and the pipeline transcribes it, picks the moments worth
cutting, writes the titles and posts, cuts the clips, and publishes them:

| | |
| --- | --- |
| ![The projects page](images/projects_page.png) | ![A project's clip grid](images/project_details.png) |
| Every project you have. | One card per highlight, with every action on it. |

## Why This Exists

Managing and clipping long form video content is tedious and time consuming. Open-Clip streamlines this workflow by providing a central dashboard to organize projects, manage metadata, and handle the heavy lifting of video processing.

## Quick Start

Ensure you have [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed on your machine.

1. Clone the repository:
   ```bash
   git clone <your-repository-url>
   cd open-clip
   ```

2. Optionally override the defaults (ports, torch build):
   ```bash
   cp .env.example .env
   ```

3. Build and start the stack:
   ```bash
   docker compose up --build
   ```
   The first build is long: it installs ffmpeg, torch and the Whisper and YOLO
   stacks. Later starts reuse the layers.

4. Access the services:
   - **Frontend**: [http://localhost:5173](http://localhost:5173)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)

5. Add your Gemini API key on the app's Settings page. It is stored in
   `backend/config/secrets.json`, which is mounted into the container, so it
   survives a rebuild and is never baked into the image.

6. [Learn how to use the application in our User Guide →](docs/USER_GUIDE.md)

### What runs where

| Path | Kept in | Why |
| --- | --- | --- |
| `./projects` | Bind mount | Project media and metadata, readable from the host. |
| `./backend/config` | Bind mount | Settings and secrets, editable by hand. |
| `backend-logs` | Named volume | Log files; the same lines also go to `docker compose logs`. |
| `youtube-credentials` | Named volume | The OAuth token, written after a YouTube sign-in. |
| `model-cache` | Named volume | Whisper and YOLO weights, so they download once. |

Port `8090` is published as well as `8000`: it is the loopback address Google
redirects to during a YouTube sign-in, and the flow cannot complete without it.

The image installs the CPU build of torch. For an NVIDIA host, set
`TORCH_INDEX_URL` in `.env` to a CUDA build and give the `backend` service a GPU
reservation.

## Features

*   **Project Management**: Organize, view, and track your video projects.
*   **Automated Clipping**: Efficient video splitting and processing.
*   **Animated Captions**: Word-by-word karaoke subtitles built from the transcript, styled and previewed in the browser before they are burned into a clip.
*   **Shorts Thumbnails**: Every clip shows the still it would be published with — by default its first frame, with the clip's title drawn on and no subtitles — drawn live in the browser, with any frame choosable instead, subtitles shown and extra text added. The picture itself is rendered at upload.
*   **Metadata Management**: Track project details via JSON metadata.
*   **Containerized Workflow**: Simple setup using Docker.

## Project Structure

*   `/backend`: Python API and processing logic.
*   `/frontend`: TypeScript and React web interface.
*   `/projects`: Local storage for project data and media.

## Development and Testing

### Backend
Navigate to the `backend` directory. The project uses `pytest` for testing.
```bash
# Example
./.venv/bin/pytest tests/unit/
```

### Frontend
Navigate to the `frontend` directory. The project uses `playwright` for end to end testing and `npm` for scripts.
```bash
npm install
npm run test
```

### Documentation screenshots
The pictures in `images/` are taken from the standard project — *First Project*,
the demo that ships in `projects/` — so the same run produces the same pictures
on any machine. With the stack running, regenerate them after a change to the
interface:
```bash
cd frontend && node scripts/docs-screenshots.mjs
```
The script keeps each file's name, because `README.md` and `docs/USER_GUIDE.md`
embed them by name. It draws a placeholder over the YouTube client secrets
before the shutter, so a configured machine does not publish its OAuth client.

### Containers
`docker/smoke-test.sh` builds both images, starts the stack and checks that it
works rather than merely that it built — the API and its media serving, the
frontend's routing and baked-in API address, ffmpeg with libass, OpenCV, the
YOLO weights, the caption fonts, the writability of every mount, and that no
secrets reached the image. CI runs the same script.
```bash
./docker/smoke-test.sh              # build, test, stop the containers
KEEP_UP=1 ./docker/smoke-test.sh    # leave the stack running afterwards
```

## Contributing

We welcome contributions. Please check `CONTRIBUTING.md` if available, or submit a pull request with a detailed description of your changes.

## Security

Please report any security vulnerabilities by opening a private GitHub Security Advisory in this repository.

## License

AGPL v3 © The Open-Clip Authors
