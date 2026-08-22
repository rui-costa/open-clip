"""The endpoint the project page polls while a pipeline runs.

It is hit every couple of seconds by every open page, and it is the only thing
that reports a running step, so a handler that raises here is silent in the log
— the request line is written before the exception — and shows up only as a
traceback on the server's terminal and an empty reply in the browser. That is
what this covers: the response has to actually come back.
"""

import json
import threading
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer

import pytest

from backend.api import SimpleHandler

PROJECT_ID = "test-project"


@pytest.fixture
def status_url(tmp_path, monkeypatch):
    """One project with a rendered clip and a step already finished."""
    project_dir = tmp_path / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True)
    (project_dir / "metadata.json").write_text(json.dumps({
        "project_id": PROJECT_ID,
        "name": "Test Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [{
            "highlight_text": "And we just lost", "viral_hook_text": "",
            "video_description_for_x": "", "video_description_for_reddit": "",
            "video_description_for_linkedin": "", "video_title_for_youtube_short": "",
            "start": 10.0, "end": 14.0, "is_clip_generated": True,
        }],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {"aspect_ratio": "9:16", "resolution": "1080p"},
        "status": None,
        "step_statuses": {"transcript": "completed"},
    }))
    monkeypatch.chdir(tmp_path)

    server = ThreadingHTTPServer(('127.0.0.1', 0), SimpleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}/project/{PROJECT_ID}/execution_status"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_answers_with_the_project_s_step_statuses(status_url):
    response = urllib.request.urlopen(status_url)
    payload = json.loads(response.read())

    assert response.status == 200
    assert payload["transcript"] == "completed"
    assert payload["progress"] == {"generated": 1, "total": 1}


def test_carries_the_clock_the_page_measures_elapsed_time_against(status_url):
    """`now` is `time.time()` on the server.

    It went out through a `time` the module never imported, so every poll was a
    NameError: the page got an empty reply and the terminal got a traceback,
    while the log recorded nothing but the request.
    """
    payload = json.loads(urllib.request.urlopen(status_url).read())

    assert isinstance(payload["now"], float)
    assert payload["now"] > 0


def test_reports_what_each_running_step_is_doing(status_url):
    payload = json.loads(urllib.request.urlopen(status_url).read())

    # Nothing is running in a freshly loaded project, but the key is always
    # there: the page reads it without checking, and a missing one is a crash
    # in the browser rather than an empty panel.
    assert payload["activity"] == {}
