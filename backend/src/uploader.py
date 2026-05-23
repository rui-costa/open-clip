import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)


class LocalCredentialProvider:
    """Manages YouTube API credentials stored locally."""

    def __init__(self, credentials_dir: str):
        self.credentials_dir = credentials_dir
        os.makedirs(self.credentials_dir, exist_ok=True)
        self.credential_file = os.path.join(self.credentials_dir, "youtube_credentials.json")

    def load(self, name: str) -> Optional[Dict[str, Any]]:
        """Load credentials from local file."""
        if os.path.exists(self.credential_file):
            with open(self.credential_file, "r") as f:
                return json.load(f)
        return None

    def save(self, name: str, data: Dict[str, Any]) -> None:
        """Save credentials to local file."""
        with open(self.credential_file, "w") as f:
            json.dump(data, f, indent=4)



class YoutubeUploader:
    """Handles video uploads to YouTube using the Google API."""

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(self, credentials_dir: str, client_secrets_config: Dict[str, Any]):
        """Initialize the YouTube uploader.
        
        Args:
            credentials_dir: Directory to store YouTube API credentials
            client_secrets_config: Dictionary containing client secrets
        """
        self.provider = LocalCredentialProvider(credentials_dir)
        if not client_secrets_config:
            raise ValueError("client_secrets_config must be provided.")
        self.client_secrets_config = client_secrets_config
        self.youtube: Optional[Any] = None

    def authenticate(self) -> None:
        """Authenticate with the YouTube API using OAuth2."""
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        token_data = self.provider.load("youtube")
        credentials = None

        if token_data:
            credentials = Credentials.from_authorized_user_info(token_data, self.SCOPES)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
                    self.client_secrets_config, self.SCOPES
                )
                credentials = flow.run_local_server()

            self.provider.save("youtube", json.loads(credentials.to_json()))

        self.youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
        logger.info("Successfully authenticated with YouTube API.")

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        category_id: str = "22",
        tags: Optional[list] = None,
        privacy_status: str = "private",
    ) -> Dict[str, Any]:
        """Upload a video to YouTube.
        
        Args:
            file_path: Path to the video file to upload
            title: Title for the video
            description: Description for the video
            category_id: YouTube category ID (default: 22 for "People & Blogs")
            tags: List of tags for the video
            privacy_status: Privacy status ("private" (default), "public", or "unlisted")
            
        Returns:
            Dictionary containing video ID, URL, and metadata
        """
        if not self.youtube:
            self.authenticate()

        if tags is None:
            tags = []

        body = {
            "snippet": {
                "categoryId": category_id,
                "title": title + " #shorts",
                "description": description,
                "tags": tags,
            },
            "status": {"privacyStatus": privacy_status},
        }

        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=googleapiclient.http.MediaFileUpload(
                file_path, chunksize=-1, resumable=True
            ),
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload {int(status.progress() * 100)}%")

        logger.info(f"Video uploaded with ID: {response['id']}")

        return {
            "video_id": response["id"],
            "url": f"https://www.youtube.com/watch?v={response['id']}",
            "title": title,
            "description": description,
            "file_path": file_path,
        }
