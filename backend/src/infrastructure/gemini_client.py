import logging
import json
import os
import re
from typing import Any, Dict, List, Optional

from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tenacity.wait import wait_base
import httpx

# Attempting safe imports
try:
    import google
    from google.genai import Client as GenAIClient
    from google.genai.errors import ClientError, ServerError
except ImportError:
    GenAIClient = None
    ClientError = None
    ServerError = None

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"
# Attempts against one model before moving down the list in models.json. Kept
# low because switching models beats waiting out a busy one.
MAX_ATTEMPTS_PER_MODEL = 4
MAX_BACKOFF_SECONDS = 60.0
RETRY_INITIAL_SECONDS = 5.0


def describe_error(exception: BaseException) -> str:
    """Renders an SDK error with its status code and server message, which repr() alone hides."""
    if isinstance(exception, RetryError) and exception.last_attempt.failed:
        inner = exception.last_attempt.exception()
        return f"gave up after {exception.last_attempt.attempt_number} attempts: {describe_error(inner)}"
    code = getattr(exception, "code", None)
    status = getattr(exception, "status", None)
    message = getattr(exception, "message", None) or str(exception)
    parts = [p for p in (f"HTTP {code}" if code else None, status, message) if p]
    return f"{type(exception).__name__}: " + " | ".join(parts)


def _status_code(exception: BaseException) -> Optional[int]:
    code = getattr(exception, "code", None)
    return code if isinstance(code, int) else None


def suggested_delay(exception: BaseException) -> Optional[float]:
    """The server's own retry hint, when the error carries a RetryInfo detail.

    Quota errors say how long the window has left ("Please retry in 2.01s");
    honouring that beats guessing with pure exponential backoff.
    """
    payload = getattr(exception, "details", None) or getattr(exception, "response_json", None)
    if isinstance(payload, dict):
        details = payload.get("error", payload).get("details")
        if isinstance(details, list):
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                if str(detail.get("@type", "")).endswith("RetryInfo"):
                    match = re.match(r"^([\d.]+)s$", str(detail.get("retryDelay", "")))
                    if match:
                        return float(match.group(1))

    # Some responses only carry the hint in prose.
    match = re.search(r"retry in ([\d.]+)s", str(getattr(exception, "message", "") or exception))
    return float(match.group(1)) if match else None


class wait_server_hint(wait_base):
    """Exponential backoff, extended when the server asks for a longer wait."""

    def __init__(self, fallback: wait_base):
        self.fallback = fallback

    def __call__(self, retry_state) -> float:
        base = self.fallback(retry_state)
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        hint = suggested_delay(exception) if exception else None
        if hint is None:
            return base
        return min(max(base, hint), MAX_BACKOFF_SECONDS)


def _is_retryable(exception: BaseException) -> bool:
    """True for transient errors worth retrying against the same model."""
    if isinstance(exception, (httpx.ReadError, httpx.ConnectError, httpx.ReadTimeout)):
        return True
    if ClientError is not None and isinstance(exception, ClientError):
        return _status_code(exception) == 429
    if ServerError is not None and isinstance(exception, ServerError):
        return True
    return False


def is_model_unavailable(exception: BaseException) -> bool:
    """True when another model is likely to succeed where this one did not.

    Quota exhaustion, overload and a missing model are all properties of the
    model, not of the prompt; a 400 on malformed input would fail identically
    everywhere, so it is not worth re-sending.
    """
    if isinstance(exception, RetryError) and exception.last_attempt.failed:
        return is_model_unavailable(exception.last_attempt.exception())
    if isinstance(exception, (httpx.ReadError, httpx.ConnectError, httpx.ReadTimeout)):
        return True
    code = _status_code(exception)
    return code in (404, 429, 500, 502, 503, 504)


class GeminiClient:
    """
    Infrastructure wrapper for Google Generative AI interactions.
    Encapsulates SDK authentication, model configuration, and model invocation.

    Requests walk the model list in backend/config/models.json: each model gets
    a few jittered, server-hint-aware retries, and an overloaded or
    quota-exhausted model hands over to the next one instead of failing the step.
    """

    def __init__(self, api_key: str, model_name: str = None):
        self.api_key = api_key
        self.models = [model_name] if model_name else self._load_models()
        self.model_name = self.models[0]
        self._client = self._initialize_client()

    @staticmethod
    def _models_path() -> str:
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "models.json"
        )

    def _load_models(self) -> List[str]:
        """The configured model preference order, most preferred first."""
        try:
            with open(self._models_path(), "r") as f:
                models = [m for m in json.load(f).get("models", []) if isinstance(m, str)]
                if models:
                    return models
                logger.warning(f"No models configured, falling back to {DEFAULT_MODEL}")
        except Exception as e:
            logger.warning(f"Could not load models, falling back to {DEFAULT_MODEL}: {e}")
        return [DEFAULT_MODEL]

    def _initialize_client(self) -> Any:
        if not self.api_key:
            raise ValueError("API Key is required for GeminiClient")

        # New SDK logic check
        if GenAIClient is not None:
            return GenAIClient(api_key=self.api_key)

        # Fallback to legacy SDK if needed
        if hasattr(google, "GenerativeModel"):
            return google.GenerativeModel(self.api_key)

        raise ImportError("No suitable Google client SDK installed")

    def _generate_once(self, model: str, prompt: str, is_json: bool) -> str:
        config: Dict[str, Any] = {"response_mime_type": "application/json"} if is_json else {}

        if hasattr(self._client, "models"):
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
        else:
            response = self._client.generate_content(model=model, contents=prompt)

        return getattr(response, "text", str(response))

    def _generate_with_retry(self, model: str, prompt: str, is_json: bool) -> str:
        def before_sleep(retry_state):
            logger.warning(
                f"{model}: retryable error (attempt {retry_state.attempt_number}), retrying in "
                f"{retry_state.next_action.sleep:.1f}s: {describe_error(retry_state.outcome.exception())}"
            )

        retryer = Retrying(
            stop=stop_after_attempt(MAX_ATTEMPTS_PER_MODEL),
            # Jittered so three steps started together stop retrying in lockstep.
            wait=wait_server_hint(
                wait_exponential_jitter(initial=RETRY_INITIAL_SECONDS, max=MAX_BACKOFF_SECONDS, jitter=5)
            ),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
            before_sleep=before_sleep,
        )
        return retryer(self._generate_once, model, prompt, is_json)

    def generate_content(self, prompt: str, is_json: bool = True) -> str:
        last_error: Optional[BaseException] = None

        for index, model in enumerate(self.models):
            try:
                if index:
                    logger.info(f"Retrying request on fallback model {model}")
                return self._generate_with_retry(model, prompt, is_json)
            except Exception as e:
                last_error = e
                remaining = self.models[index + 1:]
                if remaining and is_model_unavailable(e):
                    logger.warning(
                        f"Model {model} unavailable ({describe_error(e)}); "
                        f"falling back to {remaining[0]}"
                    )
                    continue
                raise

        raise last_error if last_error else RuntimeError("No models configured")
