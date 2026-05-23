import pytest
from unittest.mock import MagicMock, patch
from backend.src.uploader import YoutubeUploader, LocalCredentialProvider

@pytest.fixture
def uploader(tmp_path):
    return YoutubeUploader(
        credentials_dir=str(tmp_path), 
        client_secrets_config={"web": {"client_id": "test", "client_secret": "test"}}
    )

def test_local_credential_provider(tmp_path):
    provider = LocalCredentialProvider(str(tmp_path))
    data = {"token": "xyz"}
    provider.save("test", data)
    assert provider.load("test") == data

@patch('googleapiclient.http.MediaFileUpload')
@patch('google.oauth2.credentials.Credentials.refresh')
@patch('backend.src.uploader.googleapiclient.discovery.build')
@patch('backend.src.uploader.LocalCredentialProvider.load')
def test_upload_video(mock_load, mock_build, mock_refresh, mock_media, uploader):
    mock_load.return_value = {
        "refresh_token": "fake_refresh",
        "client_id": "fake_id",
        "client_secret": "fake_secret"
    }
    
    # Setup mock chain for youtube.videos().insert()
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube
    mock_insert = mock_youtube.videos().insert
    mock_request = mock_insert.return_value
    mock_request.next_chunk.return_value = (None, {'id': 'vid123'})
    
    result = uploader.upload_video("test.mp4", "Title", "Desc")
    assert result['video_id'] == 'vid123'
    assert mock_insert.called
