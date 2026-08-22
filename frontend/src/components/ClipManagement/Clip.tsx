import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ConfirmationModal } from '../ConfirmationModal';
import { Button } from '../Button';
import {
  uploadClipThumbnail,
  getClipVideoUrl,
  getClipCaptions,
  getClipThumbnail,
  type ClipPreview,
} from '../../api';
import { ThumbnailPreview } from './ThumbnailPreview';
import { Tooltip } from '../Tooltip';
import { CaptionOverlay } from './CaptionOverlay';
import { ClipPlayer } from './ClipPlayer';
import { TextOverlay } from './TextOverlay';
import { OverlayTextEditor } from './OverlayTextEditor';
import { ThumbnailEditor } from './ThumbnailEditor';
import { formatTimecode } from '../../utils/aspectRatio';
import { useInViewport } from '../../hooks/useInViewport';
import { describeRequestFailure, useClipRender } from '../../hooks/useClipRender';
import { useClipUpload } from '../../hooks/useClipUpload';
import { ClipCaptionSettings, type CaptionPreviewSource } from './ClipCaptionSettings';
import { DEFAULT_OVERLAY_TEXT, type OverlayText } from '../../api';

export interface ClipData {
  /** Position in the project's highlights, which is what the grid renders. */
  index: number;
  /** Null until the clipper has actually cut this highlight. */
  filename: string | null;
  isRendered: boolean;
  /** True once the rendered file has captions in its own pixels. */
  captionsBurned?: boolean;
  /** True once the rendered file has the overlay title in its own pixels. */
  overlayBurned?: boolean;
  /** When the file was last cut. The filename does not change between renders. */
  renderedAt?: string | null;
  /**
   * What this clip would be published as: the YouTube Short title the video
   * meta step wrote. Absent until that step has run.
   */
  title?: string;
  /** The model's hook for this moment, which the card falls back to. */
  hook?: string;
  /**
   * Where this clip already lives on YouTube, once it has been published.
   *
   * The card carries it for the same reason the detail page does: uploading
   * again publishes a second video rather than replacing the first, and a
   * button that looks untouched is how that happens by accident.
   */
  youtubeUrl?: string | null;
  /** The published video's id, which is what addresses its Studio edit page. */
  youtubeVideoId?: string | null;
  /** When this clip was last published, which is how a finished upload job is
   *  told from one that gave up. */
  uploadedAt?: string | null;
  original_start: number;
  original_end: number;
  text: string;
}

interface ClipProps {
  projectId: string;
  clip: ClipData;
  /** The uncut source video, played inside the highlight's window until the
   *  clipper renders a real file. */
  sourceUrl: string | null;
  /** Target width / height the clipper would render at, or null for source. */
  aspectRatio: number | null;
  /**
   * What every card in this project shows while it is still: the clip's
   * thumbnail, or the video frame under it. A project setting rather than a
   * card one — a grid where some cards show stills and others show footage is
   * not a comparison of anything.
   */
  clipPreview?: ClipPreview;
  onDelete: (index: number) => void;
  playingClipIndex: number | null;
  setPlayingClipIndex: (index: number | null) => void;
  /** Stagger offset for the grid's entrance. */
  enterDelayMs?: number;
}

const ClipCard: React.FC<ClipProps> = ({ projectId, clip, sourceUrl, aspectRatio, clipPreview = 'thumbnail', onDelete, playingClipIndex, setPlayingClipIndex, enterDelayMs = 0 }) => {
  const [isConfirming, setIsConfirming] = useState(false);
  // Publishing is irreversible from here, so it is guarded on the card exactly
  // as it is on the detail page. The grid is the faster place to click, which
  // is a reason for the guard rather than against it.
  const [isConfirmingUpload, setIsConfirmingUpload] = useState(false);
  const [isEditingCaptions, setIsEditingCaptions] = useState(false);
  const [isEditingOverlay, setIsEditingOverlay] = useState(false);
  const [isEditingThumbnail, setIsEditingThumbnail] = useState(false);
  // What the overlay editor is typing, held here so the card's own picture
  // redraws per keystroke rather than waiting for the save to come back.
  const [overlayDraft, setOverlayDraft] = useState<OverlayText | null>(null);
  const [isSendingThumbnail, setIsSendingThumbnail] = useState(false);
  // One banner for both actions on this card: an upload and a re-cut are the
  // two things it can report, and only one of them runs at a time.
  const [actionResult, setActionResult] = useState<{ ok: boolean; message: string } | null>(null);
  const navigate = useNavigate();
  const isRendered = clip.isRendered && !!clip.filename;

  // Captured once at mount, so this is true only for a clip that was still a
  // preview when the page opened and finished rendering while the user
  // watched. Opening a project whose clips were all rendered days ago sweeps
  // nothing. Lazy state rather than a ref because a ref may not be read during
  // render; the initialiser runs once and the value never changes after.
  const [wasPreviewAtMount] = useState(() => !isRendered);
  const celebrateRender = isRendered && wasPreviewAtMount;
  const videoSrc = isRendered
    ? getClipVideoUrl(projectId, clip.filename as string, clip.renderedAt)
    : null;
  // What the card shows before it is played: this clip's thumbnail, drawn
  // rather than fetched. The picture itself is not made until the clip is
  // published, and there is nothing in it the page cannot draw — a frame of
  // the clip with text over it, which is what the player is already doing.
  const wantsThumbnail = clipPreview === 'thumbnail';
  // Also while the caption dialog is open: it plays this same clip behind a
  // scrim, and two copies of one clip playing over each other is two soundtracks.
  const shouldPause =
    isEditingCaptions ||
    isEditingOverlay ||
    isEditingThumbnail ||
    (playingClipIndex !== null && playingClipIndex !== clip.index);
  const [mediaRef, hasApproached] = useInViewport<HTMLDivElement>();

  // What the card is called: what this clip would be published as, which is the
  // one string that names the clip rather than quotes it. The video meta step
  // writes it, so a project that has only found its highlights falls back to
  // the hook, and a project with neither to the clip's position.
  const cardLabel =
    clip.title?.trim() || clip.hook?.trim() || `Clip ${clip.index + 1}`;

  // Cached per clip by react-query, so the grid asks once per card and the
  // detail page reuses the same entry.
  const { data: captions } = useQuery({
    queryKey: ['clipCaptions', projectId, clip.index],
    queryFn: () => getClipCaptions(projectId, clip.index),
    // Deferred with the player. Firing on mount meant one request per
    // highlight the moment the page opened, all for cards nobody had scrolled
    // to yet.
    enabled: hasApproached,
    // Cues only change when the caption settings do, and CaptionStyler already
    // invalidates this key when they are saved. Without a staleTime every
    // remount of the grid refetched all of them.
    staleTime: 5 * 60_000,
  });
  // A file with captions already in it must not get them drawn again.
  const overlayCues = captions && captions.cues.length > 0 && !clip.captionsBurned ? captions : null;

  // Which frame the thumbnail is, and what it says. Asked for only when the
  // project shows thumbnails, and only once the card is worth drawing at all.
  const { data: thumbnail } = useQuery({
    queryKey: ['clipThumbnail', projectId, clip.index],
    queryFn: () => getClipThumbnail(projectId, clip.index),
    enabled: hasApproached && wantsThumbnail,
    staleTime: 5 * 60_000,
  });
  // Drawn only when there is a source to take the frame out of: the still is
  // cut from the original video, not from this clip's file, so a project whose
  // source has gone cannot show one.
  const thumbnailWhileStill = wantsThumbnail && !!thumbnail && !!sourceUrl;

  // The title as it stands: what is being typed, or what the clip resolves to
  // — its own if it has unlocked one, otherwise the project's — or the values a
  // new one starts from. Resolved by the backend and delivered by the same
  // preview request the captions arrive on.
  const overlayText = overlayDraft ?? captions?.overlay ?? DEFAULT_OVERLAY_TEXT;
  // A resolved title is always present now that the project has one, so the
  // words are what say whether this clip carries a title at all.
  const hasTitle = !!overlayText.text.trim();
  // Its own rather than the project's: the icon marks the clip that is the
  // exception, which is what the caption lock beside it marks too.
  const ownsTitle = captions ? !captions.overlay_locked : false;
  // Same rule the captions follow: a title already in the file's pixels is not
  // drawn over itself. While the editor is open it is drawn regardless, because
  // that is the only way to see the edit.
  const showTitle =
    hasTitle &&
    overlayText.enabled &&
    (isEditingOverlay || !clip.overlayBurned);

  // What the caption dialog places its captions on. The cut file when there is
  // one and it is still clean; otherwise the source inside this highlight's
  // window, which is what the next render will be cut from anyway.
  const useSourceForCaptionPreview = !isRendered || !!clip.captionsBurned;
  const captionPreviewSrc = useSourceForCaptionPreview ? sourceUrl : videoSrc;
  const captionPreview: CaptionPreviewSource | null = captionPreviewSrc
    ? {
        src: captionPreviewSrc,
        start: useSourceForCaptionPreview ? clip.original_start : 0,
        end: useSourceForCaptionPreview ? clip.original_end : null,
        isPreview: useSourceForCaptionPreview,
        aspectRatio,
        label: cardLabel,
      }
    : null;

  // Same choice for the title, decided on the title's own burn flag: a file
  // that already carries it would show the edit and the burned copy at once.
  // Burned captions are no reason to avoid the file here — they are not what is
  // being placed.
  const useSourceForOverlayPreview = !isRendered || !!clip.overlayBurned;
  const overlayPreviewSrc = useSourceForOverlayPreview ? sourceUrl : videoSrc;
  const overlayPreview: CaptionPreviewSource | null = overlayPreviewSrc
    ? {
        src: overlayPreviewSrc,
        start: useSourceForOverlayPreview ? clip.original_start : 0,
        end: useSourceForOverlayPreview ? clip.original_end : null,
        isPreview: useSourceForOverlayPreview,
        aspectRatio,
        label: cardLabel,
      }
    : null;

  // The thumbnail is cut from the *source* — the clipper's own crop applied to
  // one frame of it — so the source window is the honest thing to pick a frame
  // out of, whatever the rendered file happens to carry. The cut file only
  // stands in for a project whose source has gone.
  const thumbnailPreview: CaptionPreviewSource | null = sourceUrl
    ? {
        src: sourceUrl,
        start: clip.original_start,
        end: clip.original_end,
        isPreview: true,
        aspectRatio,
        label: cardLabel,
      }
    : videoSrc
      ? { src: videoSrc, start: 0, end: null, isPreview: false, aspectRatio, label: cardLabel }
      : null;

  // The same re-cut the clip detail page runs, from the grid: a title or a
  // caption change is made per clip, and having to open each clip to burn it in
  // is the slow half of a fast edit.
  const { isRendering, start: startRender } = useClipRender({
    projectId,
    clipIndex: clip.index,
    renderedAt: clip.renderedAt,
    onFinished: setActionResult,
  });

  // Watched like the re-cut, because publishing now begins with one: the clip
  // is cut afresh so what goes up is the clip this card is showing.
  const { isUploading, start: startUpload } = useClipUpload({
    projectId,
    clipIndex: clip.index,
    uploadedAt: clip.uploadedAt,
    onFinished: setActionResult,
  });

  const handleRegenerate = () => {
    setActionResult(null);
    void startRender();
  };

  const handleUploadThumbnail = async () => {
    if (isSendingThumbnail) return;
    setActionResult(null);
    setIsSendingThumbnail(true);
    try {
      await uploadClipThumbnail(projectId, clip.index);
      setActionResult({ ok: true, message: 'Thumbnail sent to YouTube' });
    } catch (error) {
      console.error('Thumbnail upload failed:', error);
      setActionResult({
        ok: false,
        message: describeRequestFailure(error, 'Could not set the thumbnail'),
      });
    } finally {
      setIsSendingThumbnail(false);
    }
  };

  const handleUpload = () => {
    // The dialog closes on confirm, but a second confirm can land while the
    // first request is still in flight — and this one publishes.
    if (isUploading) return;
    setIsConfirmingUpload(false);
    setActionResult(null);
    void startUpload();
  };

  return (
    <div
      className="clip-card"
      style={{
        padding: '0',
        backgroundColor: 'var(--bg)',
        border: 'var(--border)',
        animationDelay: `${enterDelayMs}ms`,
        position: 'relative',
      }}
    >
      {/* Fires the moment the clipper turns this card from a preview into a
          real file — the one instant where something the user waited for
          actually arrives. */}
      {celebrateRender && (
        <span className="sweep-clip" aria-hidden="true">
          <span className="sweep-band sweep-band--success" />
        </span>
      )}

      {/* Every card below the fold used to mount a <video> pointed at the full
          source, so a project with twenty highlights opened twenty media
          elements and twenty range requests against the same multi-gigabyte
          file on first paint. Browsers cap concurrent media decoders and
          connections, so the later cards simply stalled. The player is mounted
          when the card comes near the viewport; until then the space is
          reserved so arriving media shifts nothing. */}
      <div
        ref={mediaRef}
        className="clip-card__media"
        // Accent for the clip being cut right now, which is the same thing it
        // means in the pipeline row above. An outline rather than a border so
        // the picture does not resize when a render starts, and inset so the
        // ring sits inside the card's own 4px edge instead of doubling it.
        style={
          isRendering
            ? {
                outline: 'var(--border-width) solid var(--accent)',
                outlineOffset: 'calc(-1 * var(--border-width))',
              }
            : undefined
        }
      >
        {/* State and timecode, over the picture. They had a row each of their
            own above the player, which on a grid of a dozen cards was a dozen
            rows of chrome for two facts that fit in a corner. */}
        <div className="clip-card__overlay">
          {/* Only the preview state is worth a pill. "Rendered" restated what
              the card already shows — a cut file playing from its own start. */}
          {!isRendered && (
            <span
              className="status-badge"
              style={{
                backgroundColor: '#000',
                color: '#F9F9F9',
                borderColor: '#F9F9F9',
              }}
            >
              Preview
            </span>
          )}
          <span
            style={{
              // Holds the right edge on a rendered card, where the pill beside
              // it is gone and `space-between` has nothing to push against.
              marginLeft: 'auto',
              padding: '2px 6px',
              backgroundColor: '#000',
              color: '#F9F9F9',
              fontSize: '0.65rem',
              fontWeight: 900,
              letterSpacing: '0.05em',
              whiteSpace: 'nowrap',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {formatTimecode(clip.original_start)}–{formatTimecode(clip.original_end)}
          </span>
        </div>

        {!hasApproached ? (
          <div
            aria-hidden="true"
            className="clip-media-placeholder"
            style={{
              aspectRatio: String(aspectRatio ?? 16 / 9),
              backgroundColor: '#000',
              width: '100%',
            }}
          />
        ) : isRendered || sourceUrl ? (
          // One player either way. A card that renders while you watch keeps
          // the same frame and the same transport; only what it is playing
          // changes, from a window inside the source to the cut file.
          <ClipPlayer
            src={isRendered ? (videoSrc as string) : (sourceUrl as string)}
            start={isRendered ? 0 : clip.original_start}
            end={isRendered ? null : clip.original_end}
            isPreview={!isRendered}
            aspectRatio={aspectRatio}
            label={cardLabel}
            shouldPause={shouldPause}
            cues={captions?.cues}
            renderOverlay={
              overlayCues || showTitle || thumbnailWhileStill
                ? (position, isPlaying) => {
                    // Untouched at the top of the clip: the card is standing in
                    // for the thumbnail, so it shows the thumbnail — its own
                    // frame of the source, over the player entirely. Playing
                    // it, or scrubbing anywhere, is asking for the video.
                    if (thumbnailWhileStill && !isPlaying && position < 0.05) {
                      return (
                        <ThumbnailPreview
                          src={sourceUrl as string}
                          sourceTime={clip.original_start + thumbnail!.settings.frame_time}
                          aspectRatio={aspectRatio}
                          settings={thumbnail!.settings}
                          title={thumbnail!.title}
                          font={thumbnail!.title_font}
                          captions={captions}
                        />
                      );
                    }
                    return (
                      <>
                        {overlayCues && (
                          <CaptionOverlay
                            cues={overlayCues.cues}
                            style={overlayCues.style}
                            font={overlayCues.font}
                            time={position}
                          />
                        )}
                        {showTitle && (
                          <TextOverlay
                            overlay={overlayText}
                            font={captions?.overlay_font}
                            time={position}
                            // A card sits parked on one frame, which is exactly
                            // where the fade-in has ramped to nothing.
                            still={!isPlaying}
                          />
                        )}
                      </>
                    );
                  }
                : undefined
            }
            onPlay={() => setPlayingClipIndex(clip.index)}
            onPause={() => {
              if (playingClipIndex === clip.index) {
                setPlayingClipIndex(null);
              }
            }}
          />
        ) : (
          <div role="status" style={{ padding: 'var(--space-xl)', backgroundColor: '#000', color: '#F9F9F9', textAlign: 'center', fontSize: '0.8rem' }}>
            No source video to preview from.
          </div>
        )}
      </div>

      {/* Two lines, under the picture rather than above it. At three lines and
          1.1rem this was the tallest thing on the card that was not the video,
          and the card is opened for the clip, not for the sentence. The full
          text is a hover away and on the detail page. */}
      <p className="clip-card__title" title={cardLabel}>
        {cardLabel}
      </p>

      <div className="clip-card__actions">
        <Tooltip
          text={
            isUploading
              ? 'Cutting the clip again, then publishing it…'
              : clip.youtubeUrl
                ? 'Upload to YouTube again — this publishes a second video'
                : 'Upload to YouTube — the clip is cut again first'
          }
        >
          <Button
            variant="primary"
            onClick={() => setIsConfirmingUpload(true)}
            // Offered for a clip nobody has rendered: the upload cuts it first.
            // Refused while a re-cut is running, which writes the same file.
            disabled={isUploading || isRendering}
            aria-busy={isUploading}
            aria-label={
              isUploading
                ? 'Uploading clip to YouTube'
                : clip.youtubeUrl
                  ? 'Upload this clip to YouTube again'
                  : 'Upload clip to YouTube'
            }
            style={{
              // Icon stays 14px; the hit area does not.
              padding: '0.25rem',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent)',
              borderColor: 'var(--accent)',
              // Stays --bg while uploading. A --text-muted fill put the accent
              // label at 1.2:1 against its own button, hiding the control at
              // the one moment it has something to report; aria-busy carries
              // the state instead.
              backgroundColor: 'var(--bg)',
            }}
          >
            {isUploading ? '...' : (
              <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
            )}
          </Button>
        </Tooltip>

        {/* Only for a clip that is already on YouTube, and deliberately not
            behind the publish confirmation: the video keeps its id, its views
            and its comments, and only the still changes. This is how a
            thumbnail edited after the upload reaches the video, and how a clip
            published before the uploader sent the file on disk gets it. */}
        {clip.youtubeVideoId && (
          <Tooltip
            text={
              isSendingThumbnail
                ? 'Sending the thumbnail…'
                : 'Put this clip’s thumbnail on the video already published'
            }
          >
            <Button
              variant="ghost"
              onClick={handleUploadThumbnail}
              disabled={isSendingThumbnail || isUploading}
              aria-busy={isSendingThumbnail}
              aria-label="Upload this clip's thumbnail to the published video"
              style={{
                padding: '0.25rem',
                minWidth: '44px',
                minHeight: '44px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {isSendingThumbnail ? '...' : (
                // A picture with an arrow leaving it: the still, going up.
                <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="5" width="18" height="14" rx="2" />
                  <circle cx="8.5" cy="10" r="1.5" />
                  <polyline points="8 19 13 13 17 16" />
                  <polyline points="19 11 19 3" />
                  <polyline points="16 6 19 3 22 6" />
                </svg>
              )}
            </Button>
          </Tooltip>
        )}

        <Tooltip
          text={
            clip.captionsBurned
              ? 'Captions: already in this file — re-render to change them'
              : captions?.locked === false
                ? 'Captions: custom for this clip'
                : 'Captions: following the project'
          }
        >
          <Button
            variant="ghost"
            onClick={() => setIsEditingCaptions(true)}
            aria-label={
              clip.captionsBurned
                ? 'Caption settings, already burned into this file'
                : captions?.locked === false
                  ? 'Caption settings, custom for this clip'
                  : 'Caption settings, following the project'
            }
            style={{
              padding: 'var(--space-sm)',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              // Three states, and the palette already had all three. Success
              // when the words are in the file's own pixels: that is done, and
              // it is the only one of the three a re-render cannot undo.
              // Accent when this clip is off on its own — the exception, which
              // is what accent means everywhere else on the card. A locked
              // clip looks like every other card.
              ...(clip.captionsBurned
                ? { backgroundColor: 'var(--success)', color: 'var(--on-success)', borderColor: 'var(--success)' }
                : {
                    color: captions?.locked === false ? 'var(--accent)' : 'var(--text)',
                    borderColor: captions?.locked === false ? 'var(--accent)' : undefined,
                  }),
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              {captions?.locked === false ? (
                // Open shackle: this clip is off on its own.
                <>
                  <rect x="3" y="11" width="18" height="11" rx="1" />
                  <path d="M7 11V7a5 5 0 0 1 9.9-1" />
                </>
              ) : (
                <>
                  <rect x="3" y="11" width="18" height="11" rx="1" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </>
              )}
            </svg>
          </Button>
        </Tooltip>

        <Tooltip
          text={
            isRendering
              ? 'Rendering this clip…'
              : isUploading
                ? 'This clip is being uploaded, which re-cuts it'
                : isRendered
                  ? 'Re-render with the current settings'
                  : 'Render this clip'
          }
        >
          <Button
            variant="ghost"
            onClick={handleRegenerate}
            // An upload is cutting this same clip, into the same file.
            disabled={isRendering || isUploading}
            aria-busy={isRendering}
            aria-label={isRendered ? 'Re-render this clip' : 'Render this clip'}
            style={{
              padding: '0.25rem',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text)',
            }}
          >
            {/* Circling arrow: the same cut, made again. Spun while the encode
                runs, which is the only motion on a card that is otherwise
                waiting. */}
            <svg
              className={isRendering ? 'spin' : undefined}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 12a9 9 0 1 1-3.5-7.1" />
              <polyline points="21 3 21 9 15 9" />
            </svg>
          </Button>
        </Tooltip>

        <Tooltip
          text={
            clip.overlayBurned
              ? 'Overlay text: already in this file — re-render to change it'
              : ownsTitle
                ? 'Edit this clip\u2019s own overlay text'
                : hasTitle
                  ? 'Overlay text: following the project\u2019s'
                  : 'Add overlay text'
          }
        >
          <Button
            variant="ghost"
            onClick={() => setIsEditingOverlay(true)}
            aria-label={
              clip.overlayBurned
                ? 'Overlay text, already burned into this file'
                : hasTitle
                  ? 'Edit overlay text'
                  : 'Add overlay text'
            }
            style={{
              padding: 'var(--space-sm)',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              // The same three states as the caption lock beside it, read the
              // same way: burned in is done, a title of its own is the
              // exception, neither is every other card.
              ...(clip.overlayBurned
                ? { backgroundColor: 'var(--success)', color: 'var(--on-success)', borderColor: 'var(--success)' }
                : {
                    color: ownsTitle ? 'var(--accent)' : 'var(--text)',
                    borderColor: ownsTitle ? 'var(--accent)' : undefined,
                  }),
            }}
          >
            {/* A capital T on a baseline: the mark for "type over this". */}
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 5h14M12 5v11" />
              <path d="M4 21h16" />
            </svg>
          </Button>
        </Tooltip>

        <Tooltip text="Edit thumbnail">
          <Button
            variant="ghost"
            onClick={() => setIsEditingThumbnail(true)}
            aria-label="Edit this clip's thumbnail"
            style={{
              padding: 'var(--space-sm)',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text)',
            }}
          >
            {/* A framed picture: the still that stands for the clip. No accent
                state, unlike the lock and the title beside it — every rendered
                clip has a thumbnail, so having one is not the exception. */}
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="1" />
              <path d="M3 16l5-5 4 4 3-3 6 6" />
              <circle cx="9" cy="9" r="1.2" />
            </svg>
          </Button>
        </Tooltip>

        <Tooltip text="View Details">
          <Button 
            variant="ghost"
            onClick={() => navigate(`/project/${projectId}/clip/${clip.index}`)}
            aria-label="View clip details"
            style={{
              // Icon stays 14px; the hit area does not.
              padding: '0.25rem',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text)',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </Button>
        </Tooltip>

        <Tooltip text="Delete Highlight">
          <Button
            variant="danger"
            onClick={() => setIsConfirming(true)}
            aria-label="Delete highlight"
            style={{
              // Icon stays 14px; the hit area does not.
              padding: '0.25rem',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--error)',
              borderColor: 'var(--error)'
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </Button>
        </Tooltip>
      </div>

      {actionResult && (
        <div
          // A failed upload or render is not a status update — it needs
          // announcing, and it needs to be dismissible, because it otherwise
          // sat on the card for the rest of the session with no way to clear it.
          role={actionResult.ok ? 'status' : 'alert'}
          style={{
            margin: '0 var(--space-md) var(--space-md) var(--space-md)',
            padding: 'var(--space-sm)',
            border: `var(--border-width) solid ${actionResult.ok ? 'var(--success)' : 'var(--error)'}`,
            color: actionResult.ok ? 'var(--text)' : 'var(--error)',
            fontSize: '0.8rem',
            fontWeight: 900,
            textAlign: 'left',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 'var(--space-sm)',
          }}
        >
          {/* Server messages can be a long sentence or an unbroken identifier. */}
          <span style={{ minWidth: 0, overflowWrap: 'anywhere', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            {actionResult.ok && (
              // Drawn on rather than simply appearing: these are the actions
              // that cost minutes or leave the app entirely, so the
              // confirmation is worth a beat.
              <svg
                className="check-draw"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                aria-hidden="true"
                fill="none"
                stroke="var(--success)"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ flexShrink: 0 }}
              >
                <path d="M4 12l5 5L20 6" />
              </svg>
            )}
            {actionResult.message}
          </span>
          <button
            type="button"
            onClick={() => setActionResult(null)}
            aria-label="Dismiss message"
            style={{
              flexShrink: 0,
              minWidth: '44px',
              minHeight: '44px',
              border: 'none',
              background: 'transparent',
              color: 'inherit',
              cursor: 'pointer',
              fontWeight: 900,
            }}
          >
            ✕
          </button>
        </div>
      )}

      <ClipCaptionSettings
        projectId={projectId}
        clipIndex={clip.index}
        captions={captions}
        preview={captionPreview}
        isOpen={isEditingCaptions}
        onClose={() => setIsEditingCaptions(false)}
      />

      <OverlayTextEditor
        projectId={projectId}
        clipIndex={clip.index}
        isOpen={isEditingOverlay}
        // The draft goes with the dialog: it has already been sent, and keeping
        // it would draw it over a clip whose stored title has since changed.
        onClose={() => {
          setIsEditingOverlay(false);
          setOverlayDraft(null);
        }}
        value={overlayText}
        onChange={setOverlayDraft}
        isBurned={!!clip.overlayBurned}
        isLocked={captions?.overlay_locked ?? false}
        // The card may be scrolled anywhere, or behind the scrim, so this
        // dialog carries its own picture rather than drawing onto the card.
        preview={overlayPreview}
        font={captions?.overlay_font}
      />

      <ThumbnailEditor
        projectId={projectId}
        clipIndex={clip.index}
        isOpen={isEditingThumbnail}
        onClose={() => setIsEditingThumbnail(false)}
        // Its own picture, like the other two dialogs: the card may be
        // scrolled anywhere, and picking a frame means scrubbing one.
        preview={thumbnailPreview}
        captions={captions}
      />

      <ConfirmationModal
        isOpen={isConfirmingUpload}
        title="Upload to YouTube"
        message={[
          cardLabel
            ? `Publish this clip to YouTube as "${cardLabel}"?`
            : 'Publish this clip to YouTube?',
          // Said before the click, because it is why the upload takes minutes
          // and why the file on disk is about to be replaced.
          'The clip is cut again from its current settings first, so what goes up is what this card shows.',
          clip.youtubeUrl
            ? 'This clip has already been published; uploading adds a second video rather than replacing it.'
            : '',
          'It goes to your channel straight away and cannot be taken down from here.',
        ]
          .filter(Boolean)
          .join(' ')}
        confirmText="UPLOAD"
        onConfirm={handleUpload}
        onCancel={() => setIsConfirmingUpload(false)}
      />

      <ConfirmationModal
        isOpen={isConfirming}
        title="Delete Highlight"
        message={
          isRendered
            ? 'This deletes the highlight and the clip rendered from it, and removes it from the marker and chapter exports. This action cannot be undone.'
            : 'This deletes the highlight and removes it from the marker and chapter exports. This action cannot be undone.'
        }
        onConfirm={() => {
          onDelete(clip.index);
          setIsConfirming(false);
        }}
        onCancel={() => setIsConfirming(false)}
      />
    </div>
  );
};

/**
 * Memoised because the project page polls twice a second while a step runs,
 * and each card owns a mounted <video>. Without this, every tick re-rendered
 * every card in the grid; with it, a tick only touches the cards whose own
 * data actually moved.
 */
export const Clip = React.memo(ClipCard);
