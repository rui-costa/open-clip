# Single Responsibility Principles: Backend Services

This document outlines the **Single Responsibility Principle (SRP)** for each backend service in the `open-clip` project. Each service is solely responsible for managing its own lifecycle, artifact cleanup, and state transitions.

## 1. Orchestrator (`PipelineOrchestrator`)
**Responsibility:** **State Coordination.**
- The Orchestrator manages the pipeline flow and execution order.
- It initiates the execution sequence (`reset` -> `start` -> `task` -> `end`) but **does not** know the internal details of how to clean up files or update metadata fields.
- It relies on service-level methods to maintain state consistency.

## 2. Transcriber (`Transcriber`)
**Responsibility:** **Audio/Video-to-Text Processing.**
- Manages the transcription lifecycle.
- **`reset_metadata`**: Clears `transcription.txt` and `word_map.csv`.
- **Service Lifecycle**: Initializes the Whisper model, processes audio, and manages transcription-related metadata status.

## 3. LLM Service (`LLMQuery`)
**Responsibility:** **Content Intelligence (LLM Tasks).**
- Manages LLM interaction for promtp callsß.
- **`reset_metadata`**: Clears artifacts (e.g., highlights) from the project state.
- **Service Lifecycle**: Orchestrates LLM prompt execution, timestamp resolution, and status updates for tasks.

## 4. Clipper (`Clipper`)
**Responsibility:** **Video Manipulation.**
- Manages video cutting, cropping, and rendering.
- **`reset_metadata`**: Clears the `clips/` directory and resets associated clip metadata (clips list, start/end times).
- **Service Lifecycle**: Configures resolution/aspect ratio, tracks subject movement, performs clipping, and saves clip-related metadata.

## 5. Uploader (`Uploader`)
**Responsibility:** **External Platform Integration.**
- Manages API authentication and video upload execution.
- **`reset_metadata`**: Clears upload-related artifacts or status in metadata.
- **Service Lifecycle**: Manages upload state, API chunking, and finalizes the upload status.

---

### Execution Protocol
Every service *must* implement the following three-step lifecycle protocol invoked by the Orchestrator:
1. **`reset_metadata(project)`**: Ensures the service is in a pristine state by deleting stale artifacts and clearing relevant project metadata fields.
2. **`start_service(project)`**: Invokes `reset_metadata` to prepare the environment for a new execution run.
3. **`end_service(project)`**: Finalizes the service execution, updating project status to 'completed'.
