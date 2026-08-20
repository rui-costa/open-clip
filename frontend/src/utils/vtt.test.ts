import { describe, it, expect } from 'vitest';
import { cuesToVtt } from './vtt';
import type { CaptionCue } from '../api';

const cue = (start: number, end: number, text: string): CaptionCue => ({
  start,
  end,
  text,
  words: [],
});

describe('cuesToVtt', () => {
  it('emits a WEBVTT header even with no usable cues', () => {
    expect(cuesToVtt([])).toMatch(/^WEBVTT\n/);
  });

  it('formats timestamps as hh:mm:ss.mmm', () => {
    const vtt = cuesToVtt([cue(0, 1.5, 'hello')]);
    expect(vtt).toContain('00:00:00.000 --> 00:00:01.500');
  });

  it('carries hours past the one hour mark', () => {
    const vtt = cuesToVtt([cue(3661.25, 3662, 'late')]);
    expect(vtt).toContain('01:01:01.250 --> 01:01:02.000');
  });

  it('drops cues whose timings would break the parser', () => {
    const vtt = cuesToVtt([
      cue(5, 5, 'zero length'),
      cue(9, 4, 'reversed'),
      cue(NaN, 2, 'not a number'),
      cue(1, 2, 'keeper'),
    ]);
    expect(vtt).toContain('keeper');
    expect(vtt).not.toContain('zero length');
    expect(vtt).not.toContain('reversed');
    expect(vtt).not.toContain('not a number');
  });

  it('escapes an arrow in cue text so it cannot start a timing line', () => {
    const vtt = cuesToVtt([cue(0, 1, 'this --> that')]);
    expect(vtt).toContain('this → that');
    // The only "-->" left is the real timing line.
    expect(vtt.match(/-->/g)).toHaveLength(1);
  });

  it('survives a missing text field', () => {
    const vtt = cuesToVtt([{ start: 0, end: 1, words: [] } as unknown as CaptionCue]);
    expect(vtt).toMatch(/^WEBVTT\n/);
    expect(vtt).toContain('00:00:00.000 --> 00:00:01.000');
  });
});
