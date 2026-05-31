import logging
import json
import os
from typing import Any, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

# Attempting safe imports
try:
    import google
    from google.genai import Client as GenAIClient
except ImportError:
    GenAIClient = None

logger = logging.getLogger(__name__)

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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.ReadError)
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
