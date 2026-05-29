import csv
from dataclasses import dataclass
from typing import List, Any

@dataclass
class TranscriptionResult:
    text: str
    word_map: List[List[Any]]

    def save_word_map(self, path: str):
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["word", "start", "end"])
            writer.writerows(self.word_map)

    def save_transcription_text(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.text)

def parse_whisper_result(result: dict) -> TranscriptionResult:
    """Parses raw Whisper output into a clean TranscriptionResult object."""
    full_text = result.get("text", "").strip()
    word_map_rows = []
    
    for segment in result.get("segments", []):
        if "words" in segment:
            for w in segment["words"]:
                word = w.get("word", "").strip().replace(",", "")
                start = round(w.get("start", 0), 2)
                end = round(w.get("end", 0), 2)
                word_map_rows.append([word, start, end])
                
    return TranscriptionResult(text=full_text, word_map=word_map_rows)
