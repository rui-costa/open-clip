import os
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from typing import Dict, Any

class YoutubeClient:
    """
    Manages the YouTube API service handle and the implementation of upload logic.
    """
    def __init__(self, credentials_path: str = "backend/youtube_credentials/youtube_credentials.json"):
        creds = None
        if os.path.exists(credentials_path):
            creds = Credentials.from_authorized_user_file(credentials_path, ['https://www.googleapis.com/auth/youtube.upload'])
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise Exception("Valid credentials not found. Please authenticate.")
        
        self.service = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    def upload_video(self, file_path: str, title: str, description: str) -> Dict[str, Any]:
        body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": "private"},
        }
        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=googleapiclient.http.MediaFileUpload(file_path, chunksize=-1, resumable=True),
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
        return {"video_id": response["id"], "url": f"https://youtube.com/watch?v={response['id']}"}
