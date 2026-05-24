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
