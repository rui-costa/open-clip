"""The handle a clip goes to Postiz through.

Postiz is a social media scheduler — self-hosted or cloud — that holds one post
per channel and sends it at a time the user picks. This application does not
schedule anything: it hands Postiz the finished clip and the text that goes
with it, as a draft the user opens, looks at, and sends. That division is
deliberate. Publishing straight to a platform is irreversible from here, and
Postiz already owns the calendar, the per-platform settings, and the preview.

Three calls make up the whole integration:

- `list_integrations` names the channels the user has connected, so the app can
  ask which ones a clip should be imported for rather than guessing.
- `upload_file` puts the rendered mp4 in Postiz's own storage and returns the
  id a post refers to it by. Postiz never fetches from this application, which
  is what makes the integration work for a backend nobody can reach.
- `create_post` writes the post itself.

The API is one flat key in a header — no OAuth, no refresh, nothing to expire —
so unlike the YouTube client there is no session to keep alive and this class
holds only configuration.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


# Postiz's cloud API. A self-hosted instance serves the same routes under
# `/api`, which `normalize_api_url` sorts out.
CLOUD_API_URL = "https://api.postiz.com/public/v1"

# Sending a rendered short is a file upload over somebody's home connection, so
# it gets its own budget; everything else is a small JSON round trip.
UPLOAD_TIMEOUT_SECONDS = 600.0
REQUEST_TIMEOUT_SECONDS = 30.0

# What Postiz accepts for a video, from its media library documentation: 1GB a
# file (images are held to 10MB, which nothing here sends). Checked before the
# transfer starts so an oversized clip fails in a second rather than after the
# whole upload.
#
# The 50MB figure that turns up around Postiz is a different limit: it is the
# JSON body cap on the post-creation routes, which is exactly why a clip is
# uploaded to `/upload` first and the post only refers to the id it returns.
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


class PostizError(Exception):
    """Postiz refused a request, or could not be reached."""


class MissingPostizCredentialsError(PostizError):
    """No Postiz API key has been configured.

    Its own type because it is the one failure the user can fix without leaving
    the app: paste a key into settings and try again. Everything else is a
    server, a network, or a channel that is not connected.
    """


class PostizRejectedPostsError(PostizError):
    """Postiz refused the post because some of its channels were not valid.

    Every channel travels in one request, so one channel Postiz will not accept
    — a Discord with no channel id, an X post missing a reply setting — takes
    the other five down with it. Postiz says which, by position: its complaints
    are addressed `posts.4.settings.channel`, and `positions` is those numbers.

    Its own type so the caller can drop exactly those channels and send the
    rest, rather than losing the whole clip to one misconfigured account.
    """

    def __init__(self, message: str, positions: Set[int]):
        super().__init__(message)
        self.positions = positions


class PostizRateLimitError(PostizError):
    """Postiz is rate limiting this key.

    Separate because the answer is "wait", not "fix something": the create-post
    endpoint allows 90 requests an hour, which a project with many clips
    imported one after another can reach.
    """


def normalize_api_url(raw: Optional[str]) -> str:
    """The base URL to call, from whatever the user pasted into settings.

    A user copies the address of their Postiz from the browser, which is the
    web app rather than the API — `https://postiz.example.com`. Self-hosted
    instances serve the API under `/api/public/v1` and the cloud serves it under
    `/public/v1`, which is not a difference anybody should have to know about,
    so the host decides and the suffix is added here.

    A URL that already names a version is left exactly as it is: it is the way
    out of this guess when an instance is behind a proxy that rewrites paths.
    """
    url = (raw or "").strip().rstrip("/")
    if not url:
        return CLOUD_API_URL
    if "://" not in url:
        url = f"https://{url}"
    if "/public/v1" in url:
        return url
    host = (urlparse(url).hostname or "").lower()
    suffix = "/public/v1" if host == "api.postiz.com" else "/api/public/v1"
    return f"{url}{suffix}"


class PostizClient:
    """Talks to one Postiz instance with one API key.

    Both are read from the application settings when they are not passed in,
    the same way the rest of the app reads its configuration, so tests can hand
    over their own without touching the settings file.
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        if api_url is None or api_key is None:
            # Imported here rather than at module scope: the settings manager
            # reads a file on import, and this module is imported by tests that
            # supply their own configuration.
            from backend.src.settings_manager import settings_manager

            if api_url is None:
                api_url = settings_manager.get("postiz_api_url")
            if api_key is None:
                api_key = settings_manager.get("postiz_api_key")

        key = str(api_key or "").strip()
        if not key:
            raise MissingPostizCredentialsError(
                "No Postiz API key is configured. Add one in Settings — it is in "
                "Postiz under Settings, Public API."
            )
        self.api_url = normalize_api_url(api_url)
        self.api_key = key

    def _headers(self) -> Dict[str, str]:
        # Postiz takes the key bare, with no `Bearer` in front of it. An OAuth
        # token (`pos_…`) goes in the same header and is not told apart here.
        return {"Authorization": self.api_key}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.api_url}{path}"
        timeout = kwargs.pop("timeout", REQUEST_TIMEOUT_SECONDS)
        try:
            response = httpx.request(
                method, url, headers=self._headers(), timeout=timeout, **kwargs
            )
        except httpx.HTTPError as e:
            raise PostizError(f"Could not reach Postiz at {url}: {e}") from e

        if response.status_code == 401:
            raise MissingPostizCredentialsError(
                "Postiz rejected the API key. Check it in Settings against the key "
                "in Postiz under Settings, Public API."
            )
        if response.status_code == 429:
            # The limit is the instance's, not a constant: the cloud allows 100
            # posts an hour, a default self-hosted instance 30, and `API_LIMIT`
            # moves it. Quoting a number this app made up sends the user
            # looking for a limit nobody set.
            limit = response.headers.get("X-RateLimit-Limit")
            allowance = f" It allows {limit} an hour." if limit else ""
            raise PostizRateLimitError(
                f"Postiz is rate limiting this key.{allowance} Wait a while and "
                "import the rest."
            )
        if response.status_code == 413:
            # Postiz itself takes video up to 1GB, so a rendered clip that comes
            # back too large was almost certainly stopped in front of it: nginx
            # defaults to a 1MB body, and Cloudflare caps a free plan at 100MB.
            # Naming that is the difference between a fixable setting and an
            # apparently arbitrary refusal.
            raise PostizError(
                f"The upload was refused as too large ({method} {path}). Postiz "
                "accepts video up to 1GB, so the limit is likely the proxy in "
                "front of it — raise `client_max_body_size` on nginx, or the "
                "equivalent on whatever is serving the instance."
            )
        if response.status_code >= 400:
            body = _short_body(response)
            positions = _rejected_positions(response)
            if positions:
                raise PostizRejectedPostsError(
                    f"Postiz would not accept {len(positions)} of the channels: {body}",
                    positions,
                )
            raise PostizError(
                f"Postiz answered {response.status_code} to {method} {path}: {body}"
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise PostizError(
                f"Postiz answered {method} {path} with something that is not JSON: "
                f"{_short_body(response)}"
            )

    def list_integrations(self) -> List[Dict[str, Any]]:
        """The channels connected to this Postiz account.

        Each one carries at least an `id` — what a post is addressed to — a
        `name`, and the platform it posts to, which Postiz calls `identifier`
        (`x`, `linkedin`, `youtube`, …). A channel Postiz has marked
        `disabled` is returned as it stands: whether to offer it is the page's
        decision, not this method's.
        """
        payload = self._request("GET", "/integrations")
        if isinstance(payload, dict):
            # Older instances wrap the list; newer ones return it bare.
            payload = payload.get("integrations", [])
        if not isinstance(payload, list):
            raise PostizError("Postiz did not return a list of channels.")
        return [entry for entry in payload if isinstance(entry, dict)]

    def list_posts(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Every post Postiz will admit to between two moments.

        One entry per channel, carrying the `state` Postiz has it in
        (`PUBLISHED`, `QUEUE`, `ERROR`), the `group` that ties the channels of
        one post together, and — once it is out — the `releaseURL`, which is the
        post on the platform itself rather than anything in Postiz.

        **Drafts are not in it.** A draft filed through this API comes back from
        nothing: not this endpoint, and there is no per-post route to ask
        instead. So a post that is absent here has either not been sent yet or
        has been deleted, and this cannot tell those apart — which is why the
        caller must never read absence as deletion.

        The window is required: without both dates Postiz answers 400.
        """
        payload = self._request(
            "GET",
            "/posts",
            params={
                "startDate": _as_postiz_date(start),
                "endDate": _as_postiz_date(end),
            },
        )
        if isinstance(payload, dict):
            payload = payload.get("posts", [])
        if not isinstance(payload, list):
            raise PostizError("Postiz did not return a list of posts.")
        return [entry for entry in payload if isinstance(entry, dict)]

    def post_exists(self, post_id: Optional[str]) -> Optional[bool]:
        """Whether Postiz still holds a post with this id.

        The one question `GET /public/v1/posts` cannot answer. That endpoint
        omits drafts, so a post missing from it may be unsent or may be gone —
        and treating "missing" as "still a draft" is how a project came to show
        nine clips waiting in Postiz that were not in Postiz at all, each with a
        link to an empty page.

        This asks the route the web app renders `/p/{id}` from, which is not
        the versioned API and not documented as part of it: it answers a list
        with the post in it when the post is real, and an empty list when it is
        not — the same empty list an id that never existed gets.

        Returns True, False, or None when the question could not be asked. None
        is not a "no": the caller must not delete a record on a network fault.
        """
        if not post_id:
            return None
        url = f"{self.web_url()}/api/public/posts/{post_id}"
        try:
            response = httpx.get(
                url, headers=self._headers(), timeout=REQUEST_TIMEOUT_SECONDS
            )
        except httpx.HTTPError as e:
            logger.warning(f"Could not ask Postiz whether {post_id} still exists: {e}")
            return None

        if response.status_code >= 400:
            logger.warning(
                f"Postiz answered {response.status_code} asking whether {post_id} exists"
            )
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        if isinstance(payload, list):
            return bool(payload)
        if isinstance(payload, dict):
            return bool(payload.get("id") or payload.get("posts"))
        return None

    def upload_file(self, path: str) -> Dict[str, Any]:
        """Puts one file in Postiz's storage and returns its `id` and `path`.

        The id is what a post refers to the video by. Nothing about this
        application is reachable from Postiz — it is a local backend behind
        whatever the user's network is — so the bytes have to go there rather
        than a URL pointing back here.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise PostizError(f"There is no file to send at {file_path}.")

        size = file_path.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            # Refused here rather than by Postiz after the whole transfer.
            raise PostizError(
                f"{file_path.name} is {size // (1024 * 1024)}MB and Postiz takes at "
                f"most {MAX_UPLOAD_BYTES // (1024 * 1024)}MB. Render the clip at a "
                "lower resolution, or trim it."
            )

        logger.info(f"Sending {file_path} ({size} bytes) to Postiz")
        with open(file_path, "rb") as handle:
            payload = self._request(
                "POST",
                "/upload",
                files={"file": (file_path.name, handle, "video/mp4")},
                timeout=UPLOAD_TIMEOUT_SECONDS,
            )

        if not isinstance(payload, dict) or not payload.get("id"):
            raise PostizError(
                f"Postiz accepted {file_path.name} but did not say what it stored it as."
            )
        return payload

    def create_post(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Creates one post — across one or several channels — and returns what it made.

        The body is built by the caller because what belongs in it is a product
        decision (which channels, what text, draft or scheduled) rather than a
        transport one. See `backend/src/services/postiz_publisher.py`.

        Everything Postiz says is handed back, as a list, one entry per channel.
        An earlier version kept `result[0]` and dropped the rest, so a clip filed
        to six channels remembered one of them and the ids of the other five
        were lost the moment they arrived — and then had to be asked for again
        later. What Postiz says at creation is the cheapest and most certain
        answer there is; nothing here is in a position to decide which part of
        it is worth keeping.

        The whole answer is logged too, because it is the only place its shape
        is ever visible: nothing else this application does can be used to work
        out what a create returns.
        """
        result = self._request("POST", "/posts", json=payload)
        entries = result if isinstance(result, list) else [result]
        entries = [entry for entry in entries if isinstance(entry, dict)]
        logger.info(f"Postiz created {len(entries)} post entr(ies): {entries}")
        return entries

    def web_url(self) -> str:
        """The Postiz web app this API belongs to, without any path on it.

        Derived rather than returned: the API answers with ids and never says
        where a person would look at them.
        """
        base = self.api_url
        for suffix in ("/api/public/v1", "/public/v1"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        if (urlparse(base).hostname or "").lower() == "api.postiz.com":
            return "https://app.postiz.com"
        return base

    def post_url(self, post_id: Optional[str]) -> Optional[str]:
        """Where a person opens a post of theirs.

        The calendar, not the post. Postiz has a `/p/{id}` preview page, and it
        was tempting: it is one link straight to the thing. But it answers 200
        for an id that never existed, serving the same empty shell it serves for
        a draft — so as a link it lies twice over, and as a way of asking
        whether a post is still there it says yes to everything.

        `post_id` is accepted and unused so callers read as asking about one
        post. When a post is actually out, the link worth following is the
        platform's own `releaseURL`, which the sync stores.

        The site root rather than a named page: every route on a Postiz
        instance answers 307 to `/auth` when signed out, so which path holds the
        calendar cannot be checked from here — and a signed-in user landing on
        the root is taken to it anyway.
        """
        return self.web_url()


# Postiz validates the array it was sent and complains per element:
# `posts.4.settings.channel should not be null or undefined`. The number is the
# position in the array this request built, which is the only way back to the
# channel that caused it.
_POST_POSITION = re.compile(r"\bposts\.(\d+)\.")


def _rejected_positions(response: httpx.Response) -> Set[int]:
    """Which entries of a rejected `posts` array Postiz complained about.

    Empty for anything that is not a per-channel validation failure — a bad
    key, a server fault, an unreadable body — because dropping channels is only
    the right answer when channels are what was wrong.
    """
    if response.status_code != 400:
        return set()
    return {int(match) for match in _POST_POSITION.findall(response.text or "")}


def _as_postiz_date(when: datetime) -> str:
    """A moment in the shape Postiz reads: milliseconds and a trailing Z."""
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _short_body(response: httpx.Response) -> str:
    """The readable part of an error body.

    Long enough to carry every complaint in a validation failure: Postiz sends
    one line per invalid field per channel, and the six-channel case ran past
    300 characters, which cut the list off before the interesting half.
    """
    text = (response.text or "").strip().replace("\n", " ")
    return text[:1200] if text else "(no body)"
