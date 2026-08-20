import { useEffect, useMemo } from 'react';
import type { CaptionCue } from '../api';

/** `hh:mm:ss.mmm`, the only timestamp form WebVTT accepts. */
const vttTimestamp = (seconds: number): string => {
  const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
  const hours = Math.floor(safe / 3600);
  const mins = Math.floor((safe % 3600) / 60);
  const secs = Math.floor(safe % 60);
  const millis = Math.round((safe - Math.floor(safe)) * 1000);
  return (
    `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}:` +
    `${String(secs).padStart(2, '0')}.${String(millis).padStart(3, '0')}`
  );
};

/**
 * Cues as a WebVTT document.
 *
 * Cue times are already relative to the start of the clip, which is what a
 * track attached to the clip's own video element needs.
 */
export const cuesToVtt = (cues: CaptionCue[]): string => {
  const body = cues
    // A zero- or negative-length cue is dropped rather than emitted: the
    // parser rejects the whole block on the first bad timing line.
    .filter((cue) => Number.isFinite(cue.start) && Number.isFinite(cue.end) && cue.end > cue.start)
    .map((cue) => {
      // A bare "-->" inside cue text would start a new timing line.
      const text = (cue.text ?? '').replace(/-->/g, '→').trim();
      return `${vttTimestamp(cue.start)} --> ${vttTimestamp(cue.end)}\n${text}`;
    });

  return `WEBVTT\n\n${body.join('\n\n')}\n`;
};

/**
 * An object URL for the cues, valid for as long as the component is mounted.
 *
 * Returns null when there is nothing to caption, so the caller can omit the
 * `<track>` entirely rather than pointing it at an empty document.
 */
export const useVttUrl = (cues: CaptionCue[] | undefined): string | null => {
  // Derived rather than held in state: the <track> needs the URL on the same
  // render the video mounts, and setting state from an effect to get there
  // costs an extra render for every card in the grid.
  const url = useMemo(() => {
    if (!cues || cues.length === 0) return null;
    return URL.createObjectURL(new Blob([cuesToVtt(cues)], { type: 'text/vtt' }));
  }, [cues]);

  // Revoked on unmount and whenever the cues change, otherwise every caption
  // edit leaks a blob for the lifetime of the page.
  useEffect(() => {
    if (!url) return;
    return () => URL.revokeObjectURL(url);
  }, [url]);

  return url;
};
