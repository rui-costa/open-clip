import logging
import json
import os
import time
from typing import Any, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
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


def _is_retryable(exception: BaseException) -> bool:
    """Returns True for transient errors that should be retried: network errors, 429 rate limits, and 5xx server errors."""
    if isinstance(exception, httpx.ReadError):
        return True
    if ClientError is not None and isinstance(exception, ClientError):
        return getattr(exception, "code", 0) == 429
    if ServerError is not None and isinstance(exception, ServerError):
        return True
    return False


class GeminiClient:
    """
    Infrastructure wrapper for Google Generative AI interactions.
    Encapsulates SDK authentication, model configuration, and model invocation.
    """
    def __init__(self, api_key: str, model_name: str = None):
        self.api_key = api_key
        self.model_name = model_name or self._get_default_model()
        self._client = self._initialize_client()

    def _get_default_model(self) -> str:
        models_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "models.json")
        try:
            with open(models_path, "r") as f:
                models = json.load(f).get("models", [])
                return models[0] if models else "gemini-2.0-flash"
        except Exception as e:
            logger.warning(f"Could not load default model, falling back to gemini-2.0-flash: {e}")
            return "gemini-2.0-flash"

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

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception(_is_retryable),
        before_sleep=lambda retry_state: logger.warning(
            f"Retryable error (attempt {retry_state.attempt_number}), retrying in "
            f"{retry_state.next_action.sleep:.1f}s: {retry_state.outcome.exception()}"
        )
    )
    def generate_content(self, prompt: str, is_json: bool = True) -> str:
        config = {"response_mime_type": "application/json"} if is_json else {}
        
        if hasattr(self._client, "models"):
            response = self._client.models.generate_content(
                model=self.model_name, 
                contents=prompt, 
                config=config
            )
        else:
            response = self._client.generate_content(
                model=self.model_name, 
                contents=prompt
            )
            
        return getattr(response, "text", str(response))
