import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../Modal';
import { Button } from '../Button';
import { ClipPlayer } from './ClipPlayer';
import { CaptionOverlay } from './CaptionOverlay';
import { TextOverlay } from './TextOverlay';
import type { CaptionPreviewSource } from './ClipCaptionSettings';
import {
  DEFAULT_THUMBNAIL,
  DEFAULT_THUMBNAIL_EXTRA,
  generateClipThumbnail,
  getClipThumbnail,
  getClipThumbnailUrl,
  updateClipThumbnail,
  type CaptionPreview,
  type OverlayText,
  type ThumbnailSettings,
} from '../../api';
import { describeRequestFailure } from '../../hooks/useClipRender';

interface ThumbnailEditorProps {
  projectId: string;
  clipIndex: number;
  isOpen: boolean;
  onClose: () => void;
  /** The picture to choose a frame from: the cut clip, or the source window. */
  preview: CaptionPreviewSource | null;
  /** The clip's cues and style, for showing what the subtitles would look like. */
  captions?: CaptionPreview | null;
}

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

const checkboxRowStyle: React.CSSProperties = {
  ...labelStyle,
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--space-sm)',
  minHeight: '44px',
  cursor: 'pointer',
};

const hintStyle: React.CSSProperties = {
  margin: 'var(--space-sm) 0 0 0',
  fontSize: '0.7rem',
  color: 'var(--text-muted)',
};

const EXTRA_SLIDERS: Array<{ key: keyof OverlayText; label: string; min: number; max: number; step: number; unit: string }> = [
  { key: 'font_size_pct', label: 'Size', min: 2, max: 20, step: 0.5, unit: '% of frame' },
  { key: 'position_pct', label: 'Position', min: 0, max: 90, step: 1, unit: '% from top' },
  { key: 'max_width_pct', label: 'Width', min: 40, max: 100, step: 2, unit: '% of frame' },
];

/**
 * One clip's thumbnail: which frame it is, and what is written on it.
 *
 * The dialog exists because only two of those decisions can be made by a
 * machine. The frame is a judgement — a mouth mid-word, a blink, a cut — and
 * the words are the user's. Everything else already has an answer: the title
 * is the clip's own or the hook the model wrote for it, the subtitles are off
 * because a caption caught mid-sentence helps nobody, and the frame is the
 * first one. A user who never opens this still has a thumbnail, rendered
 * beside the clip when it was cut.
 *
 * The picture above the controls is the picker: scrub it, and the frame it is
 * showing is the frame the button takes. What is drawn over it is drawn by the
 * same description the burn reads, so the still is a promise rather than an
 * impression.
 */
export const ThumbnailEditor: React.FC<ThumbnailEditorProps> = ({
  projectId,
  clipIndex,
  isOpen,
  onClose,
  preview,
  captions = null,
}) => {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // What the debounce is still holding, kept in a ref for the same reason the
  // overlay editor keeps one: the dialog can be closed by a click on the
  // scrim, which does not re-render this component first.
  const unsavedRef = useRef<ThumbnailSettings | null>(null);
  // What the player is showing, which is what "use this frame" means.
  const [livePosition, setLivePosition] = useState(0);
  const [draft, setDraft] = useState<ThumbnailSettings | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['clipThumbnail', projectId, clipIndex],
    queryFn: () => getClipThumbnail(projectId, clipIndex),
    enabled: isOpen,
  });

  // The stored settings are the starting point, and the draft takes over from
  // the first edit: re-seeding on every refetch would drag a slider back to
  // the saved value while it was being moved.
  const settings = draft ?? data?.settings ?? DEFAULT_THUMBNAIL;
  const title = data?.title ?? null;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['clipThumbnail', projectId, clipIndex] });
    queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    queryClient.invalidateQueries({ queryKey: ['projectMetadata', projectId] });
  };

  const save = useMutation({
    mutationFn: (next: ThumbnailSettings | null) => updateClipThumbnail(projectId, clipIndex, next),
    onSuccess: invalidate,
  });

  const render = useMutation({
    mutationFn: () => generateClipThumbnail(projectId, clipIndex),
    onSuccess: (result) => {
      // The rendered file is named on the settings, so the draft has to take
      // the new name and stamp or the <img> below keeps pointing at the old
      // one — or at nothing, the first time.
      setDraft((current) => (current ? { ...current, ...result.thumbnail } : result.thumbnail));
      setFailure(null);
      invalidate();
    },
    onError: (error) => setFailure(describeRequestFailure(error, 'Could not make the thumbnail.')),
  });

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const flush = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    const unsaved = unsavedRef.current;
    unsavedRef.current = null;
    if (unsaved) save.mutate(unsaved);
  };

  const commit = (next: ThumbnailSettings) => {
    setDraft(next);
    unsavedRef.current = next;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => flush(), 300);
  };

  const set = <K extends keyof ThumbnailSettings>(key: K, next: ThumbnailSettings[K]) =>
    commit({ ...settings, [key]: next });

  const setExtra = <K extends keyof OverlayText>(key: K, next: OverlayText[K]) =>
    commit({ ...settings, extra: { ...(settings.extra ?? DEFAULT_THUMBNAIL_EXTRA), [key]: next } });

  const close = () => {
    flush();
    onClose();
  };

  const reset = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    // Dropped rather than flushed: the pending edit is to settings that are
    // about to be replaced by the defaults.
    unsavedRef.current = null;
    setDraft(null);
    save.mutate(null);
  };

  // Rounded to hundredths: the seek is to a frame, and a number with six
  // decimal places on it only reads as noise.
  const useThisFrame = () => set('frame_time', Math.round(livePosition * 100) / 100);

  const extra = settings.extra;
  const showTitle = settings.show_overlay && !!title?.text.trim();
  const imageUrl = settings.generated_filename
    ? getClipThumbnailUrl(projectId, settings.generated_filename, settings.generated_at)
    : null;

  return (
    <Modal
      isOpen={isOpen}
      title={`Thumbnail for clip ${clipIndex + 1}`}
      onClose={close}
      maxWidth="620px"
      footer={
        <>
          <Button variant="ghost" onClick={reset}>
            Back to defaults
          </Button>
          <Button variant="primary" onClick={close}>
            Save and close
          </Button>
        </>
      }
    >
      {preview && (
        // Sticky, like the caption and overlay dialogs': the picture is what
        // every control here is aimed at, so it stays put while they scroll.
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
              initialOffset={settings.frame_time}
              onPositionChange={setLivePosition}
              renderOverlay={(position) => (
                <>
                  {settings.show_captions && captions?.cues?.length ? (
                    <CaptionOverlay
                      cues={captions.cues}
                      style={captions.style}
                      font={captions.font}
                      time={position}
                    />
                  ) : null}
                  {showTitle && (
                    <TextOverlay
                      overlay={title as OverlayText}
                      font={data?.title_font}
                      time={position}
                      // A still has no fade to be part-way through, and the
                      // title is on it wherever the playhead happens to be.
                      forceVisible
                    />
                  )}
                  {extra?.text.trim() ? (
                    <TextOverlay overlay={extra} font={data?.title_font} time={position} forceVisible />
                  ) : null}
                </>
              )}
            />
          </div>
        </div>
      )}

      <p style={{ margin: '0 0 var(--space-md) 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        {isLoading
          ? 'Reading this clip’s thumbnail…'
          : 'Left alone, the thumbnail is the first frame of the clip with its title on it and no subtitles. Everything below changes that.'}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <div>
          <span style={labelStyle}>
            Frame
            <span style={{ float: 'inline-end', color: 'var(--text-muted)' }}>
              {settings.frame_time.toFixed(2)}s into the clip
            </span>
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={useThisFrame}
            disabled={!preview}
            style={{ width: '100%', minHeight: '44px', marginTop: 'var(--space-sm)' }}
          >
            Use the frame showing now ({livePosition.toFixed(2)}s)
          </Button>
          <p style={hintStyle}>
            {preview
              ? 'Scrub the clip above to the frame you want, then take it.'
              : 'There is no video to pick a frame from, so the thumbnail is the first frame.'}
          </p>
        </div>

        <label style={checkboxRowStyle}>
          <input
            type="checkbox"
            checked={settings.show_overlay}
            onChange={(event) => set('show_overlay', event.target.checked)}
            style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
          />
          Draw the clip’s title
        </label>
        {settings.show_overlay && (
          <p style={{ ...hintStyle, marginTop: 'calc(-1 * var(--space-sm))' }}>
            {title?.text.trim()
              ? `Drawn as: “${title.text}”. It is the clip’s overlay text, or the hook written for it — edit it under Overlay text.`
              : 'There is nothing to draw yet: add overlay text to this clip, or run the steps that write its hook.'}
          </p>
        )}

        <label style={checkboxRowStyle}>
          <input
            type="checkbox"
            checked={settings.show_captions}
            onChange={(event) => set('show_captions', event.target.checked)}
            style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
          />
          Show the subtitles
        </label>
        <p style={{ ...hintStyle, marginTop: 'calc(-1 * var(--space-sm))' }}>
          Off by default. Only the line being spoken on the chosen frame is drawn.
        </p>

        <div>
          <label htmlFor={`clip-${clipIndex}-thumbnail-extra`} style={labelStyle}>
            Extra text
          </label>
          <textarea
            id={`clip-${clipIndex}-thumbnail-extra`}
            value={extra?.text ?? ''}
            rows={2}
            maxLength={200}
            placeholder="Only on the thumbnail — never on the video"
            onChange={(event) => setExtra('text', event.target.value)}
            style={{ ...controlStyle, resize: 'vertical', fontFamily: 'inherit' }}
          />
          <p style={hintStyle}>A line break here is a line break on the picture.</p>
        </div>

        {extra?.text.trim() ? (
          <>
            {EXTRA_SLIDERS.map((slider) => {
              const raw = extra[slider.key];
              const numeric = typeof raw === 'number' && Number.isFinite(raw)
                ? Math.min(slider.max, Math.max(slider.min, raw))
                : slider.min;
              return (
                <div key={slider.key}>
                  <label htmlFor={`clip-${clipIndex}-thumbnail-extra-${slider.key}`} style={labelStyle}>
                    {slider.label}
                    <span style={{ float: 'inline-end', color: 'var(--text-muted)' }}>
                      {numeric} {slider.unit}
                    </span>
                  </label>
                  <input
                    id={`clip-${clipIndex}-thumbnail-extra-${slider.key}`}
                    type="range"
                    min={slider.min}
                    max={slider.max}
                    step={slider.step}
                    value={numeric}
                    onChange={(event) => setExtra(slider.key, Number(event.target.value) as never)}
                    style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer', minHeight: '44px' }}
                  />
                </div>
              );
            })}
            <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
              <label style={checkboxRowStyle}>
                <input
                  type="checkbox"
                  checked={extra.uppercase}
                  onChange={(event) => setExtra('uppercase', event.target.checked)}
                  style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
                />
                Uppercase
              </label>
              <label style={checkboxRowStyle}>
                <input
                  type="checkbox"
                  checked={Boolean(extra.box_color)}
                  // The colour doubles as the switch, here and in the ASS
                  // style: no colour means no block behind the text.
                  onChange={(event) => setExtra('box_color', event.target.checked ? '#000000CC' : null)}
                  style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
                />
                Background block
              </label>
            </div>
          </>
        ) : null}

        <div style={{ borderTop: 'var(--border)', paddingTop: 'var(--space-md)' }}>
          <Button
            variant="primary"
            onClick={() => {
              // The render reads what is stored, so anything the debounce is
              // still holding has to land first.
              flush();
              render.mutate();
            }}
            disabled={render.isPending}
            style={{ width: '100%', minHeight: '44px' }}
          >
            {render.isPending ? 'Making the picture…' : imageUrl ? 'Make it again' : 'Make the thumbnail'}
          </Button>
          <p style={hintStyle}>
            The picture is burned by the same renderer as the clip, so it is not
            an approximation of the frame — it is the frame. It is attached to
            the video when the clip is uploaded.
          </p>

          {imageUrl && (
            <div style={{ marginTop: 'var(--space-md)' }}>
              <img
                src={imageUrl}
                alt={`Thumbnail for clip ${clipIndex + 1}`}
                style={{ width: '100%', maxWidth: '220px', display: 'block', border: 'var(--border)' }}
              />
              <p style={{ ...hintStyle, marginTop: 'var(--space-sm)' }}>
                <a href={imageUrl} download={`clip_${clipIndex + 1}_thumbnail.jpg`}>
                  Download this image
                </a>
              </p>
            </div>
          )}
        </div>
      </div>

      {(failure || save.isError) && (
        <p role="alert" style={{ margin: 'var(--space-md) 0 0 0', fontSize: '0.75rem', color: 'var(--error)' }}>
          {failure ??
            'Could not save these settings. The next thumbnail would be made from whatever was last saved, not from what is on screen.'}
        </p>
      )}
    </Modal>
  );
};
