import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeAll } from 'vitest';
import { CaptionOverlay } from './CaptionOverlay';
import { stubFrameSize } from '../../test/stubFrame';
import type { CaptionCue, CaptionStyle } from '../../api';

const STYLE: CaptionStyle = {
  label: 'Karaoke Pop',
  description: '',
  animation: 'karaoke',
  words_per_cue: 4,
  font_family: 'Arial Black',
  font_size_pct: 10,
  bold: true,
  italic: false,
  uppercase: false,
  text_color: '#FFFFFF',
  active_color: '#FFE500',
  outline_color: '#000000',
  shadow_color: '#000000',
  box_color: null,
  outline_pct: 1,
  shadow_pct: 0.5,
  position_pct: 80,
  max_width_pct: 86,
  active_scale: 1.2,
};

const CUES: CaptionCue[] = [
  {
    start: 0,
    end: 1.0,
    text: 'and we just lost',
    words: [
      { text: 'and', start: 0, end: 0.25 },
      { text: 'we', start: 0.25, end: 0.5 },
      { text: 'just', start: 0.5, end: 0.75 },
      { text: 'lost', start: 0.75, end: 1.0 },
    ],
  },
  { start: 2.0, end: 2.5, text: 'them', words: [{ text: 'them', start: 2.0, end: 2.5 }] },
];

// 400px stands in for the rendered preview box; the overlay sizes everything
// from it.
beforeAll(() => stubFrameSize(400));

const overlay = (time: number, style: CaptionStyle = STYLE) =>
  render(<CaptionOverlay cues={CUES} style={style} time={time} />);

const wordSpan = (text: string) =>
  Array.from(document.querySelectorAll('span')).find((span) => span.textContent === text);

describe('CaptionOverlay', () => {
  it('shows the cue covering the current time', () => {
    overlay(0.3);
    expect(screen.getByText('just')).toBeInTheDocument();
  });

  it('shows nothing in the gap between cues', () => {
    overlay(1.5);
    expect(screen.queryByText('lost')).not.toBeInTheDocument();
    expect(screen.queryByText('them')).not.toBeInTheDocument();
  });

  // The caption editor pauses on whatever frame it likes, and a gap between
  // cues there would mean tuning placement against an empty picture.
  it('holds the nearest cue through silence when asked to', () => {
    render(<CaptionOverlay cues={CUES} style={STYLE} time={1.5} holdWhenSilent />);
    expect(screen.getByText('lost')).toBeInTheDocument();
  });

  it('holds the first cue before any of them has started', () => {
    render(
      <CaptionOverlay
        cues={[{ ...CUES[0], start: 1.0, words: CUES[0].words.map((w) => ({ ...w, start: w.start + 1 })) }]}
        style={STYLE}
        time={0}
        holdWhenSilent
      />
    );
    expect(screen.getByText('and')).toBeInTheDocument();
  });

  it('highlights the word being spoken', () => {
    overlay(0.6);
    expect(wordSpan('just')).toHaveStyle({ color: 'rgb(255, 229, 0)' });
    expect(wordSpan('we')).toHaveStyle({ color: 'rgb(255, 255, 255)' });
  });

  it('keeps a word highlighted until the next one starts', () => {
    // Matches the ASS events, where a word owns the frame up to the next start.
    overlay(0.4);
    expect(wordSpan('we')).toHaveStyle({ color: 'rgb(255, 229, 0)' });
  });

  it('scales the spoken word by the style pop factor', () => {
    overlay(0.1);
    // Type size rather than a transform: ASS `\fscy` reflows the line around
    // the word it grows, so a transform would put the word somewhere the burn
    // does not.
    expect(wordSpan('and')?.style.fontSize).toBe('48px');
    expect(wordSpan('we')?.style.fontSize).toBe('');
  });

  it('does not highlight or scale anything in a static style', () => {
    overlay(0.1, { ...STYLE, animation: 'static' });
    expect(wordSpan('and')).toHaveStyle({ color: 'rgb(255, 255, 255)' });
    expect(wordSpan('and')?.style.fontSize).toBe('');
  });

  it('separates words with a real space, the way the ASS file does', () => {
    overlay(0.1);
    const block = wordSpan('and')?.parentElement;
    expect(block?.textContent).toBe('and we just lost');
  });

  it('spaces lines by the height of the font the render will use', () => {
    // libass has no line-spacing control: it stacks lines by the font's
    // ascent-to-descent height, so the overlay has to use the same number.
    render(
      <CaptionOverlay
        cues={CUES}
        style={STYLE}
        font={{ family: 'Arial Black', height_ratio: 1.41, url: null }}
        time={0.1}
      />
    );
    const block = wordSpan('and')?.parentElement?.parentElement;
    expect(block).toHaveStyle({ lineHeight: '1.41' });
  });

  it('sizes the text as a percentage of the frame, not in fixed pixels', () => {
    overlay(0.1);
    // 10% of the 400px frame.
    const block = wordSpan('and')?.parentElement?.parentElement;
    expect(block).toHaveStyle({ fontSize: '40px' });
  });

  it('is hidden from assistive technology, which reads the transcript instead', () => {
    const { container } = overlay(0.1);
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
  });
});
