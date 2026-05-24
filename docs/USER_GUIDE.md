# User Guide

This guide walks you through the core workflow of using OpenClip to process and manage video clips.

## 1. Getting Started: Projects Page
When you launch the application, you arrive at the **Projects Page**. This is your dashboard for all video processing tasks.

![Projects Page](../images/projects_page.png)

From here, you can view existing projects or create a new one.

## 2. Uploading a Video
To start a new project, click the upload button to navigate to the **Upload Screen**.

![Upload Screen](../images/upload_screen.png)

1. Select your video file.
2. Provide necessary project details.
3. Upon submission, the project is created, and you are automatically navigated to the **Project Details** page.

## 3. Running the Pipeline and Managing Details
In the **Project Details** view, the project is initialized but not yet processed.

![Project Details](../images/project_details.png)

1. **Trigger Processing**: Click the action to start the pipeline. The interface is reactive and will update in real-time as the backend processes the video.
2. **Review Output**: Once complete, you can view the transcription, manage generated clips, and perform clip-specific actions.

## 4. Configuring Settings
You can customize the application's behavior in the **Settings Page**.

![Settings Page](../images/settings_page.png)

Adjust your configuration (API keys, models, etc.). Changes made here are saved directly to the backend `settings.json` file.
