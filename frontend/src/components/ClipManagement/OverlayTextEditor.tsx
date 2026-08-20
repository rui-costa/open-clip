import React, { useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../Modal';
import { Button } from '../Button';
import { ClipPlayer } from './ClipPlayer';
import { TextOverlay } from './TextOverlay';
import type { CaptionPreviewSource } from './ClipCaptionSettings';
import {
  DEFAULT_OVERLAY_TEXT,
  updateClipOverlay,
  type CaptionFont,
  type OverlayText,
} from '../../api';

interface OverlayTextEditorProps {
  projectId: string;
  clipIndex: number;
  isOpen: boolean;
  onClose: () => void;
  /**
   * A picture to place the title against, shown inside the dialog.
   *
   * The clip grid passes one because the card it was opened from may be
   * anywhere on a scrolled page, or behind the scrim entirely. The clip detail
   * page passes none: its player is already on screen behind this dialog and
   * draws the same draft.
   */
  preview?: CaptionPreviewSource | null;
  /** The face the burn will use, for the dialog's own preview. */
  font?: CaptionFont | null;
  /** What the preview is currently drawing: the draft if there is one, else what is stored. */
  value: OverlayText;
  /** Reports the edit so the player behind the dialog redraws as it is typed. */
  onChange: (next: OverlayText) => void;
  /** True once the rendered file already has this title in its pixels. */
  isBurned?: boolean;
}

const SLIDERS: Array<{ key: keyof OverlayText; label: string; min: number; max: number; step: number; unit: string }> = [
  { key: 'start', label: 'Starts at', min: 0, max: 30, step: 0.5, unit: 's into the clip' },
  { key: 'duration', label: 'Stays for', min: 0.5, max: 30, step: 0.5, unit: 's' },
  // Listed, and zero by default: a title that ramps up is invisible on the one
  // frame most likely to be seen, so the fade has to be a decision.
  { key: 'fade_in', label: 'Fades in over', min: 0, max: 5, step: 0.1, unit: 's' },
  { key: 'fade_out', label: 'Fades out over', min: 0, max: 5, step: 0.1, unit: 's' },
  { key: 'font_size_pct', label: 'Size', min: 2, max: 20, step: 0.5, unit: '% of frame' },
  { key: 'position_pct', label: 'Position', min: 0, max: 85, step: 1, unit: '% from top' },
  { key: 'max_width_pct', label: 'Width', min: 40, max: 100, step: 2, unit: '% of frame' },
  { key: 'outline_pct', label: 'Outline', min: 0, max: 2, step: 0.1, unit: '% of frame' },
];

const labelStyle: React.CSSProperties = {
  fontWeight: 900,
  textTransform: 'uppercase',
  fontSize: '0.7rem',
  letterSpacing: '0.05em',
};

const controlStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.4rem',
  border: '2px solid var(--border-color)',
  background: 'var(--bg)',
  color: 'var(--text)',
  fontWeight: 700,
  fontSize: '0.8rem',
  minHeight: '44px',
};

/**
 * One clip's overlay title: the text, when it shows, and how it looks.
 *
 * Every change is written to the clip rather than held here, the same contract
 * the caption settings keep: the clipper burns from what is stored, so what the
 * preview draws is a promise about the next render. Writes are debounced
 * because typing a title would otherwise be one request per keystroke.
 *
 * Saving does not touch the rendered file — nothing does until the clip is
 * re-cut — so the dialog says so rather than letting a saved title look burned.
 */
export const OverlayTextEditor: React.FC<OverlayTextEditorProps> = ({
  projectId,
  clipIndex,
  isOpen,
  onClose,
  value,
  onChange,
  isBurned = false,
  preview = null,
  font = null,
}) => {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // What the debounce is holding. Kept in a ref rather than read from `value`
  // on the way out: the dialog can be closed from a scrim click, which does not
  // re-render this component first.
  const unsavedRef = useRef<OverlayText | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);

  const invalidate = () => {
    // The stored overlay travels on the project; the face it will be drawn
    // with travels on the clip's caption preview.
    queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    queryClient.invalidateQueries({ queryKey: ['projectMetadata', projectId] });
    queryClient.invalidateQueries({ queryKey: ['clipCaptions', projectId] });
  };

  const mutation = useMutation({
    mutationFn: (next: OverlayText | null) => updateClipOverlay(projectId, clipIndex, next),
    onSuccess: invalidate,
  });

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const commit = (next: OverlayText, immediate = false) => {
    onChange(next);
    unsavedRef.current = next;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => flush(), immediate ? 0 : 300);
  };

  /**
   * Sends whatever the debounce is still holding, now.
   *
   * Every way out of this dialog goes through here, because the last keystroke
   * before a close would otherwise be sitting in a timer nobody waits for — a
   * title typed and closed in the same second was simply lost.
   */
  const flush = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    const unsaved = unsavedRef.current;
    unsavedRef.current = null;
    if (unsaved) mutation.mutate(unsaved);
  };

  const close = () => {
    flush();
    onClose();
  };

  const set = <K extends keyof OverlayText>(key: K, next: OverlayText[K]) =>
    commit({ ...value, [key]: next });

  const remove = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    // Dropped rather than flushed: the pending edit is to a title that is about
    // to stop existing, and sending it would race the removal.
    unsavedRef.current = null;
    onChange({ ...DEFAULT_OVERLAY_TEXT, enabled: false, text: '' });
    mutation.mutate(null);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      title={`Overlay text for clip ${clipIndex + 1}`}
      onClose={close}
      maxWidth={preview ? '620px' : undefined}
      initialFocusRef={textRef}
      footer={
        <>
          <Button variant="ghost" onClick={remove}>
            Remove this title
          </Button>
          {/* Redundant against the autosave, and worth having anyway: a form
              with no button to press gives the user nothing to believe. It
              sends what the debounce is still holding rather than a copy of
              what is already stored. */}
          <Button variant="primary" onClick={close}>
            Save and close
          </Button>
        </>
      }
    >
      {preview && (
        // Sticky, like the caption dialog's: the picture is what the sliders
        // are aimed at, so it stays put while they are scrolled to.
        <div
          style={{
            position: 'sticky',
            top: 'calc(-1 * var(--space-md))',
            zIndex: 1,
            background: 'var(--bg)',
            margin: 'calc(-1 * var(--space-md)) 0 var(--space-md) 0',
            padding: 'var(--space-md) 0 var(--space-sm) 0',
          }}
        >
          <div
            style={{
              border: 'var(--border)',
              marginInline: 'auto',
              maxWidth: preview.aspectRatio
                ? `calc(min(300px, 40vh) * ${preview.aspectRatio})`
                : undefined,
            }}
          >
            <ClipPlayer
              src={preview.src}
              start={preview.start}
              end={preview.end}
              isPreview={preview.isPreview}
              aspectRatio={preview.aspectRatio}
              label={preview.label}
              renderOverlay={(position) => (
                <TextOverlay
                  overlay={value}
                  font={font}
                  time={position}
                  // The title is the subject of this dialog, so it is drawn
                  // whatever the playhead is doing — including at the exact
                  // moment its fade starts, where it is otherwise invisible.
                  forceVisible
                />
              )}
            />
          </div>
        </div>
      )}
      <p style={{ margin: '0 0 var(--space-md) 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        {isBurned
          ? 'This title is already burned into the rendered file. Changing it here changes the next render, not the file you have.'
          : preview
            ? 'Saved as you type, and drawn on the clip above. Regenerate the clip to burn it into the video.'
            : 'Saved as you type, and drawn over the player behind this dialog. Regenerate the clip to burn it into the video.'}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <div>
          <label htmlFor={`clip-${clipIndex}-overlay-text`} style={labelStyle}>Text</label>
          <textarea
            id={`clip-${clipIndex}-overlay-text`}
            ref={textRef}
            value={value.text}
            rows={2}
            maxLength={200}
            placeholder="The line that opens the clip"
            onChange={(event) => set('text', event.target.value)}
            style={{ ...controlStyle, resize: 'vertical', fontFamily: 'inherit' }}
          />
          <p style={{ margin: 'var(--space-sm) 0 0 0', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            A line break here is a line break on the video.
          </p>
        </div>

        <label style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', minHeight: '44px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={value.enabled}
            onChange={(event) => set('enabled', event.target.checked)}
            style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
          />
          Burn this title into rendered clips
        </label>

        {SLIDERS.map((slider) => {
          const raw = value[slider.key];
          const numeric = typeof raw === 'number' && Number.isFinite(raw)
            ? Math.min(slider.max, Math.max(slider.min, raw))
            : slider.min;
          return (
            <div key={slider.key}>
              <label htmlFor={`clip-${clipIndex}-overlay-${slider.key}`} style={labelStyle}>
                {slider.label}
                {/* Logical, not `right`: this label is a row of two things and
                    should flip with the writing direction. */}
                <span style={{ float: 'inline-end', color: 'var(--text-muted)' }}>
                  {numeric}{slider.unit ? ` ${slider.unit}` : ''}
                </span>
              </label>
              <input
                id={`clip-${clipIndex}-overlay-${slider.key}`}
                type="range"
                min={slider.min}
                max={slider.max}
                step={slider.step}
                value={numeric}
                onChange={(event) => set(slider.key, Number(event.target.value) as never)}
                style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer', minHeight: '44px' }}
              />
            </div>
          );
        })}

        <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 40%' }}>
            <label htmlFor={`clip-${clipIndex}-overlay-text_color`} style={labelStyle}>Text colour</label>
            <input
              id={`clip-${clipIndex}-overlay-text_color`}
              type="color"
              value={value.text_color}
              onChange={(event) => set('text_color', event.target.value.toUpperCase())}
              style={{ ...controlStyle, padding: '2px', cursor: 'pointer' }}
            />
          </div>
          <div style={{ flex: '1 1 40%' }}>
            <label htmlFor={`clip-${clipIndex}-overlay-outline_color`} style={labelStyle}>Outline colour</label>
            <input
              id={`clip-${clipIndex}-overlay-outline_color`}
              type="color"
              value={value.outline_color}
              onChange={(event) => set('outline_color', event.target.value.toUpperCase())}
              style={{ ...controlStyle, padding: '2px', cursor: 'pointer' }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
          <label style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', minHeight: '44px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={value.uppercase}
              onChange={(event) => set('uppercase', event.target.checked)}
              style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
            />
            Uppercase
          </label>
          <label style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', minHeight: '44px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={Boolean(value.box_color)}
              // The box colour doubles as its on/off switch, here and in the ASS
              // style: no colour means no block behind the text.
              onChange={(event) => set('box_color', event.target.checked ? '#000000CC' : null)}
              style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
            />
            Background block
          </label>
        </div>
      </div>

      {mutation.isError && (
        <p role="alert" style={{ margin: 'var(--space-md) 0 0 0', fontSize: '0.75rem', color: 'var(--error)' }}>
          Could not save this title. The clip would render with whatever was last saved, not what is on screen.
        </p>
      )}
    </Modal>
  );
};
