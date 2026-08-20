I am providing a podcast transcript in attach and a word map with timestamps. Your task is to divide this transcript into logical chapters based on the topic of conversation.

## MANDATORY FOR EACH CHAPTER

- A short, catchy Title.
- The Start Time in [hh:mm:ss]

## MADATORY OUTPUT
[start_time] - [chapter title]

## EXAMPLE
00:00 - Intro
01:45 - James' origin story
03:20 - First fake profile encounter
05:50 - Red flags recruiters look for
...

## TRANSCRIPT:  
{transcript_text}

## WORD MAP:  
{word_map}

## OUTPUT: RETURN ONLY VALID JSON. Order by start time.
{{
  "chapters": [
    {{
      "chapter_time": "<Timestamp in HH:MM:SS>",
      "chapter_title": "<Chapter title>"
    }}
  ]
}}