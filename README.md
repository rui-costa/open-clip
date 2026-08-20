# Open-Clip

> An automated video clipping and processing engine.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Overview

Open-Clip is an automated video processing system designed to manage and clip video projects efficiently. It provides a full-stack solution featuring a Python based backend for processing and a web based frontend for project management.

## Why This Exists

Managing and clipping long form video content is tedious and time consuming. Open-Clip streamlines this workflow by providing a central dashboard to organize projects, manage metadata, and handle the heavy lifting of video processing.

## Quick Start

Ensure you have [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed on your machine.

1. Clone the repository:
   ```bash
   git clone <your-repository-url>
   cd open-clip
   ```

2. Create an `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

3. Start the development environment:
   ```bash
   docker-compose up --build
   ```

4. [Learn how to use the application in our User Guide →](docs/USER_GUIDE.md)

5. Access the services:
   - **Frontend**: [http://localhost:5173](http://localhost:5173)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)

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

## Contributing

We welcome contributions. Please check `CONTRIBUTING.md` if available, or submit a pull request with a detailed description of your changes.

## Security

Please report any security vulnerabilities by opening a private GitHub Security Advisory in this repository.

## License

AGPL v3 © The Open-Clip Authors

## Star History

<a href="https://www.star-history.com/?repos=rui-costa%2Fopen-clip&type=date&logscale=&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=rui-costa/open-clip&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=rui-costa/open-clip&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=rui-costa/open-clip&type=date&legend=top-left" />
 </picture>
</a>