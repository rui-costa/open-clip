import os
import csv
import json
import logging
import time
from google.genai import Client
from typing import Dict, Any, List
from .utils import find_highlight_timestamps
from .settings_manager import settings_manager

logger = logging.getLogger(__name__)

class LLMTaskExecutor:
    def __init__(self, model_name: str = None):
        # Strictly use settings_manager key
        self.api_key = settings_manager.get("gemini_api_key")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in settings.json")
        self.client = Client(api_key=self.api_key)
        self._load_model_order()
        self.model_name = model_name or self.models_to_try[0]
        
        if self.model_name in self.models_to_try:
            self.models_to_try = [self.model_name] + [m for m in self.models_to_try if m != self.model_name]

    def _load_model_order(self):
        models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "models.json")
        try:
            with open(models_path, "r") as f:
                data = json.load(f)
                self.models_to_try = data.get("models")
                if not self.models_to_try:
                    raise ValueError("models.json is empty")
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            logger.error(f"Could not load valid models from {models_path}.")
            raise

    def _load_transcript_text(self, text_path: str) -> str:
        """Load full transcript text from plain text file."""
        try:
            with open(text_path, "r", encoding="utf-8") as f:
                text = f.read()
            logger.info(f"Loaded transcript text ({len(text)} characters)")
            return text
        except FileNotFoundError as e:
            logger.error(f"Error loading transcript text: {e}")
            raise

    async def execute_task(
        self,
        prompt_filename: str,
        template_vars: Dict[str, Any],
        progress_callback: Any = None
    ) -> Any:
        """
        Execute a generic LLM task using a prompt template.
        """
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", prompt_filename)
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            
        with open(prompt_path, "r") as f:
            prompt_template = f.read()
            
        prompt = prompt_template.format(**template_vars)
        
        if progress_callback:
            progress_callback(0.1)
        
        max_retries = 5
        for i, model in enumerate(self.models_to_try):
            logger.info(f"Attempting task {prompt_filename} with model: {model}")
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    result = json.loads(response.text)
                    logger.info(f"Successfully executed task {prompt_filename} with {model}")
                    
                    if progress_callback:
                        progress_callback(1.0)
                        
                    return result
                    
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "500" in error_str or "INTERNAL" in error_str:
                        if attempt < max_retries - 1:
                            wait = (attempt + 1) * 5
                            logger.warning(f"Error {error_str} on model {model}, attempt {attempt+1}/{max_retries}, retrying in {wait}s...")
                            time.sleep(wait)
                            continue
                        else:
                            logger.error(f"Max retries reached for model {model}.")
                            break
                    else:
                        logger.error(f"Non-retriable error executing task with model {model}: {e}")
                        raise
            
            if progress_callback:
                progress_callback(0.1 + (i + 1) / len(self.models_to_try) * 0.8)
        
        logger.error(f"Failed to execute task {prompt_filename} after trying all models.")
        raise RuntimeError(f"Failed to execute task {prompt_filename}: all models failed.")

    async def extract_highlights(
        self, 
        transcription_text_path: str,
        word_map_csv_path: str,
        progress_callback: Any = None
    ) -> List[Dict[str, Any]]:
        """
        Extract highlights from a video transcript and resolve their timestamps.
        """
        transcript_text = self._load_transcript_text(transcription_text_path)
        
        result = await self.execute_task(
            prompt_filename="HIGHLIGHTS.md",
            template_vars={"transcript_text": transcript_text},
            progress_callback=progress_callback
        )
        
        highlights = result.get("shorts", []) if isinstance(result, dict) else result
        
        # Resolve timestamps using word_map.csv
        if word_map_csv_path and os.path.exists(word_map_csv_path):
            try:
                all_words = []
                with open(word_map_csv_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        all_words.append({
                            'w': row['word'],
                            's': float(row['start']),
                            'e': float(row['end'])
                        })
                
                for h in highlights:
                    text = h.get('highlight_text', '')
                    if text:
                        ts = find_highlight_timestamps(all_words, text)
                        h['start'] = ts['start']
                        h['end'] = ts['end']
                        
            except Exception as e:
                logger.error(f"Error resolving timestamps from word map: {e}")
        
        return highlights

    async def generate_video_metadata(
        self,
        transcription_text_path: str,
        progress_callback: Any = None
    ) -> Dict[str, Any]:
        """
        Generate video metadata (titles, summaries, etc.) from a transcript.
        """
        transcript_text = self._load_transcript_text(transcription_text_path)
        
        result = await self.execute_task(
            prompt_filename="VIDEO_META.md",
            template_vars={"transcript_text": transcript_text},
            progress_callback=progress_callback
        )
        
        return result

# Maintain backward compatibility for now
HighlightExtractor = LLMTaskExecutor
