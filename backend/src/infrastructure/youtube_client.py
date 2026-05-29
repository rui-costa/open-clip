import googleapiclient.http
from typing import Dict, Any

class YoutubeClient:
    """
    Manages the YouTube API service handle and the implementation of upload logic.
    """
    def __init__(self, youtube_service: Any):
        self.service = youtube_service

    def upload_video(self, file_path: str, title: str, description: str) -> Dict[str, Any]:
        body = {
            "snippet": {"title": title + " #shorts", "description": description},
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
