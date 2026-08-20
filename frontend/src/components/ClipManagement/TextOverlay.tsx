import React, { useEffect, useRef, useState } from 'react';
import type { CaptionFont, OverlayText } from '../../api';
import { useCaptionFont } from '../../utils/captionFont';

interface TextOverlayProps {
  overlay: OverlayText;
  /** The face the burn will use. Absent for a backend that could not resolve one. */
  font?: CaptionFont | null;
  /** Seconds from the start of the clip, not from the start of the source. */
  time: number;
  /**
   * Draws the title regardless of where playback is, at full opacity.
   *
   * Set while the editor is open. A title fading in from zero is invisible at
   * the exact moment it starts, which is where a paused preview sits — so
   * without this the honest render is a blank frame while the user types into
   * it. Playing the clip shows the real timing.
   */
  forceVisible?: boolean;
  /**
   * Skips the fade ramps while playback is stopped.
   *
   * A fade is motion, and a still frame has none to show: paused on the first
   * frame of a clip, `\fad` has not started ramping, so the honest per-frame
   * opacity is zero and a saved title looks like it was never saved. Within its
   * window a stopped player therefore draws the title solid; outside it, still
   * nothing.
   */
  still?: boolean;
}

/**
 * Draws the title the clipper would burn in, over the preview player.
 *
 * The browser half of a pair, like CaptionOverlay: the other half is
 * `build_overlay_event` in backend/src/services/ass_writer.py, which draws the
 * same object with libass at render time. Both read one description whose sizes
 * are percentages of the frame, so this stays honest at any preview size.
 *
 * The two things that have to agree are the position — anchored to the *top* of
 * the frame, because a title hangs off the top edge — and the fade, which is
 * ASS `\fad(in,out)`: a linear ramp up over `fade_in` and down over `fade_out`,
 * with the visible window in between.
 */
export const TextOverlay: React.FC<TextOverlayProps> = ({
  overlay,
  font,
  time,
  forceVisible = false,
  still = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [frameHeight, setFrameHeight] = useState(0);
  const loadedFamily = useCaptionFont(font ?? undefined);

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

  const elapsed = time - overlay.start;
  const remaining = overlay.duration - elapsed;
  // Outside its window the title is not drawn at all, rather than drawn at zero
  // opacity: a transparent block still sits over the picture.
  const isWithinWindow = forceVisible || (elapsed >= 0 && remaining > 0);
  const opacity = forceVisible || still
    ? 1
    : Math.max(
        0,
        Math.min(
          1,
          overlay.fade_in > 0 ? elapsed / overlay.fade_in : 1,
          overlay.fade_out > 0 ? remaining / overlay.fade_out : 1
        )
      );

  const fontSize = (frameHeight * overlay.font_size_pct) / 100;
  const outlineWidth = (frameHeight * overlay.outline_pct) / 100;

  const blockStyle: React.CSSProperties = {
    position: 'absolute',
    top: `${overlay.position_pct}%`,
    left: `${(100 - overlay.max_width_pct) / 2}%`,
    width: `${overlay.max_width_pct}%`,
    margin: 0,
    textAlign: 'center',
    // libass stacks lines by the font's own ascent-to-descent height and has no
    // line-spacing control, so a two-line title only matches if this does.
    lineHeight: font?.height_ratio ?? 1.2,
    fontFamily: loadedFamily
      ? `"${loadedFamily}", "${overlay.font_family}", sans-serif`
      : `"${overlay.font_family}", "Arial Black", Arial, sans-serif`,
    fontSize: `${fontSize}px`,
    // The resolved face already carries the weight and slant the render will
    // use; asking for them again only adds a synthetic version of what the file
    // already has.
    fontWeight: loadedFamily ? 400 : overlay.bold ? 900 : 400,
    fontStyle: loadedFamily ? 'normal' : overlay.italic ? 'italic' : 'normal',
    fontSynthesis: 'none',
    textTransform: overlay.uppercase ? 'uppercase' : 'none',
    color: overlay.text_color,
    // A typed line break is a line break in the burn (`\N`), so it has to be
    // one here too.
    whiteSpace: 'pre-line',
    // `paint-order` keeps the stroke behind the glyph, so a thick outline does
    // not eat into the letterforms.
    WebkitTextStroke: outlineWidth > 0 ? `${outlineWidth}px ${overlay.outline_color}` : undefined,
    paintOrder: 'stroke fill',
    opacity,
    pointerEvents: 'none',
  };

  return (
    <div
      ref={containerRef}
      // Decorative: the title is the user's own text, already on screen in the
      // editor, and announcing it per frame would flood a screen reader.
      aria-hidden="true"
      style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}
    >
      {isWithinWindow && frameHeight > 0 && (
        <div style={blockStyle}>
          <span
            style={{
              display: 'inline-block',
              padding: overlay.box_color ? `${fontSize * 0.15}px ${fontSize * 0.35}px` : undefined,
              backgroundColor: overlay.box_color ?? undefined,
            }}
          >
            {overlay.text}
          </span>
        </div>
      )}
    </div>
  );
};
