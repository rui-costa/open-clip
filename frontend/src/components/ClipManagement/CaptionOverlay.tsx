import React, { useEffect, useRef, useState } from 'react';
import type { CaptionCue, CaptionFont, CaptionStyle } from '../../api';
import { useCaptionFont } from '../../utils/captionFont';

interface CaptionOverlayProps {
  cues: CaptionCue[];
  style: CaptionStyle;
  /** The face the burn will use. Absent for a backend that could not resolve one. */
  font?: CaptionFont;
  /** Seconds from the start of the clip, not from the start of the source. */
  time: number;
  /**
   * Draw the nearest cue when no cue covers `time`.
   *
   * Off everywhere the overlay stands for the render, where silence has to draw
   * nothing. On in the caption editor, where a paused player parked on a gap
   * between cues would otherwise show an empty frame and nothing to place.
   */
  holdWhenSilent?: boolean;
}

/**
 * Draws the captions the clipper would burn in, over the preview player.
 *
 * This is the browser half of a pair: the other half is
 * backend/src/services/ass_writer.py, which draws the same cues with libass at
 * render time. Both read one style object whose sizes are percentages of the
 * frame, so this overlay stays honest at any preview size — a caption at 7% of
 * frame height is 7% here and 7% in the 1080x1920 output.
 *
 * The parts that have to match are: which words share a cue (decided on the
 * backend), which word is active at a given time (the rule below), and how the
 * block is positioned (bottom-anchored, centred, margins from the style).
 *
 * Making the two agree on *size* takes both sides doing something. This one
 * draws with the font file the backend resolved rather than with a family name,
 * and spaces its lines by that font's own ascent-to-descent height, which is
 * the only line spacing libass can produce. The writer, for its part, converts
 * this em-based font size into the ascent-to-descent number ASS expects, and
 * halves the outline because a centred CSS stroke only shows half its width.
 */
export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  cues,
  style,
  font,
  time,
  holdWhenSilent = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [frameHeight, setFrameHeight] = useState(0);
  const loadedFamily = useCaptionFont(font);

  // Percentages resolve against the rendered box, so its height has to be a
  // measured value rather than an assumed one.
  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => setFrameHeight(entry.contentRect.height));
    observer.observe(element);
    setFrameHeight(element.getBoundingClientRect().height);
    return () => observer.disconnect();
  }, []);

  const spoken = cues.find((candidate) => time >= candidate.start && time < candidate.end);
  // The last cue that has started, or the first one when nothing has yet: the
  // words nearest the playhead are the ones worth holding on to.
  const nearest = cues.reduce<CaptionCue | undefined>(
    (held, candidate) => (time >= candidate.start ? candidate : held),
    cues[0]
  );
  const cue = spoken ?? (holdWhenSilent ? nearest : undefined);

  // The active word holds until the next one starts, matching the per-word
  // events in the ASS file: the caption never blanks mid-cue.
  const activeIndex = cue
    ? cue.words.reduce((active, word, index) => (time >= word.start ? index : active), 0)
    : -1;

  const fontSize = (frameHeight * style.font_size_pct) / 100;
  const outlineWidth = (frameHeight * style.outline_pct) / 100;
  const shadowOffset = (frameHeight * style.shadow_pct) / 100;
  const animated = style.animation !== 'static';

  const blockStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: `${100 - style.position_pct}%`,
    left: `${(100 - style.max_width_pct) / 2}%`,
    width: `${style.max_width_pct}%`,
    margin: 0,
    textAlign: 'center',
    // libass has no line-spacing control: it stacks lines by the font's
    // ascent-to-descent height. Matching that is what keeps a two-line cue the
    // same height in both renderers.
    lineHeight: font?.height_ratio ?? 1.15,
    fontFamily: loadedFamily
      ? `"${loadedFamily}", "${style.font_family}", sans-serif`
      : `"${style.font_family}", "Arial Black", Arial, sans-serif`,
    fontSize: `${fontSize}px`,
    // The resolved face already carries the weight and slant the render will
    // use, so asking for them again would only add a synthetic version of what
    // the font already has.
    fontWeight: loadedFamily ? 400 : style.bold ? 900 : 400,
    fontStyle: loadedFamily ? 'normal' : style.italic ? 'italic' : 'normal',
    fontSynthesis: 'none',
    textTransform: style.uppercase ? 'uppercase' : 'none',
    color: style.text_color,
    // `paint-order` keeps the stroke behind the glyph, so a thick outline does
    // not eat into the letterforms the way a plain text-stroke does.
    WebkitTextStroke: outlineWidth > 0 ? `${outlineWidth}px ${style.outline_color}` : undefined,
    paintOrder: 'stroke fill',
    textShadow: shadowOffset > 0 ? `${shadowOffset}px ${shadowOffset}px 0 ${style.shadow_color}` : undefined,
    pointerEvents: 'none',
  };

  return (
    <div
      ref={containerRef}
      // Purely decorative: the same words are already in the transcript, and
      // announcing a re-render on every word would flood a screen reader.
      aria-hidden="true"
      style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}
    >
      {cue && frameHeight > 0 && (
        <div style={blockStyle}>
          <span
            style={{
              display: 'inline-block',
              padding: style.box_color ? `${fontSize * 0.15}px ${fontSize * 0.35}px` : undefined,
              backgroundColor: style.box_color ?? undefined,
            }}
          >
            {cue.words.map((word, index) => {
              const isActive = animated && index === activeIndex;
              return (
                <React.Fragment key={`${word.start}-${index}`}>
                  {/* A real space, not a margin: the ASS file joins words with
                      one, so the gap has to be the font's own space glyph or
                      the burned line comes out a different width. */}
                  {index > 0 ? ' ' : ''}
                  <span
                    style={{
                      display: 'inline-block',
                      color: isActive ? style.active_color : style.text_color,
                      // Type size rather than `transform`: ASS `\fscy` reflows
                      // the line around the word it grows, and a transform does
                      // not, so a scaled word would sit in a different place in
                      // each renderer.
                      fontSize: isActive ? `${fontSize * style.active_scale}px` : undefined,
                      // libass scales the border with the glyph.
                      WebkitTextStroke:
                        isActive && outlineWidth > 0
                          ? `${outlineWidth * style.active_scale}px ${style.outline_color}`
                          : undefined,
                      // 120ms is the same ramp the ASS transform uses.
                      transition: 'font-size 120ms ease-out',
                    }}
                  >
                    {word.text}
                  </span>
                </React.Fragment>
              );
            })}
          </span>
        </div>
      )}
    </div>
  );
};
