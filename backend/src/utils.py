import json

def find_highlight_timestamps(all_words, snippet):
    """
    Finds start and end timestamps for a snippet using an anchor-based approach.
    Matches a chunk of words at the start and a chunk at the end to define boundaries.
    Falls back to fuzzy matching if anchors are not found.
    """
    if not snippet:
        return {"start": 0.0, "end": 0.0}

    snippet_words = snippet.strip().split()
    if not snippet_words:
        return {"start": 0.0, "end": 0.0}
    
    normalized_snippet = [w.strip(".,!?\"'").lower() for w in snippet_words]
    CHUNK_SIZE = 5

    # --- Strategy 1: Anchor-Based Matching ---
    # Only attempt if the snippet is long enough to have distinct start/end anchors
    if len(normalized_snippet) >= CHUNK_SIZE * 2:
        start_anchor = normalized_snippet[:CHUNK_SIZE]
        end_anchor = normalized_snippet[-CHUNK_SIZE:]
        
        # Find start anchor
        start_idx = -1
        for i in range(len(all_words) - CHUNK_SIZE + 1):
            if all([all_words[i+j]['w'].strip(".,!?\"'").lower() == start_anchor[j] for j in range(CHUNK_SIZE)]):
                start_idx = i
                break
        
        if start_idx != -1:
            # Find end anchor appearing after the start anchor
            end_idx = -1
            for i in range(start_idx + CHUNK_SIZE, len(all_words) - CHUNK_SIZE + 1):
                if all([all_words[i+j]['w'].strip(".,!?\"'").lower() == end_anchor[j] for j in range(CHUNK_SIZE)]):
                    end_idx = i
                    # We take the last possible match for the end anchor to be safe
                    # but for most highlights, the first one after start_idx is correct.
            
            if end_idx != -1:
                return {
                    "start": all_words[start_idx]['s'],
                    "end": all_words[end_idx + CHUNK_SIZE - 1]['e']
                }

    # --- Strategy 2: Fallback Fuzzy Matching ---
    # Allow for small gaps between words to be resilient to LLM paraphrasing
    MAX_GAP = 3
    for i in range(len(all_words)):
        if all_words[i]['w'].strip(".,!?\"'").lower() == normalized_snippet[0]:
            current_map_idx = i
            match_count = 1
            
            while match_count < len(normalized_snippet):
                found_next = False
                for gap in range(1, MAX_GAP + 2):
                    next_idx = current_map_idx + gap
                    if next_idx >= len(all_words):
                        break
                    if all_words[next_idx]['w'].strip(".,!?\"'").lower() == normalized_snippet[match_count]:
                        current_map_idx = next_idx
                        match_count += 1
                        found_next = True
                        break
                if not found_next:
                    break
            
            if match_count == len(normalized_snippet):
                return {
                    "start": all_words[i]['s'],
                    "end": all_words[current_map_idx]['e']
                }
            
    return {"start": 0.0, "end": 0.0}
