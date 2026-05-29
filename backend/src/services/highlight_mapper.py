import json
from dataclasses import dataclass
from typing import List, Dict, Any
from backend.src.utils import find_highlight_timestamps

@dataclass
class Highlight:
    text: str
    start: float = 0.0
    end: float = 0.0

def parse_highlights(raw_response_text: str, all_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parses raw LLM output (JSON string) into a clean list of aligned highlights."""
    raw_json = json.loads(raw_response_text)
    highlights = raw_json.get("highlights", raw_json.get("shorts", []))
    
    processed = []
    for h in highlights:
        text = h.get('highlight_text', '')
        if text:
            ts = find_highlight_timestamps(all_words, text)
            h['start'] = ts['start']
            h['end'] = ts['end']
            processed.append(h)
    return processed
