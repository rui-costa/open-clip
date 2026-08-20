import React, { useId, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '../Button';
import { PipelineController } from '../PipelineController/PipelineController';
import type { StepStatus } from '../PipelineController/PipelineController';
import { ClipManager } from '../ClipManagement/ClipManager';
import { CaptionStyler } from '../ClipManagement/CaptionStyler';
import { LlmOutputs } from './LlmOutputs';
import { DescriptionPanel } from './DescriptionPanel';
import {
  updateProjectSettings,
  getMarkerEdlUrl,
  getResolutionMap,
  getAspectRatioMap,
  getExecutionStatus,
  getSourceVideoUrl,
  type ClipPreview,
  type ProjectMetadata,
} from '../../api';
import { targetAspectRatio } from '../../utils/aspectRatio';
import { stepLabel } from '../../utils/stepLabels';

interface ProjectDetailProps {
  metadata: ProjectMetadata;
  pipelineConfig: {
    execution_order: string[];
    steps?: Record<string, { auto_run?: boolean; llm?: boolean; depends_on?: string[] }>;
  };
  activeProcesses: string[];
  onExecuteAction: (action: 'START' | 'STOP', step: string) => void;
  onDeleteClip: (index: number) => void;
  onDeleteProject: () => void;
}

export const ProjectDetail: React.FC<ProjectDetailProps> = ({ metadata, pipelineConfig, activeProcesses, onExecuteAction, onDeleteClip, onDeleteProject }) => {
  const [showMetadata, setShowMetadata] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  // Which way the user paged, so the incoming panel enters from that side
  // instead of always sliding the same way.
  const [swapDirection, setSwapDirection] = useState<1 | -1>(1);
  const [sourceVideoFailed, setSourceVideoFailed] = useState(false);
  const queryClient = useQueryClient();
  const metadataPanelId = useId();
  const resolutionId = useId();
  const aspectRatioId = useId();
  const clipPreviewId = useId();

  const { data: resolutionsData } = useQuery({
    queryKey: ['resolutions'],
    queryFn: getResolutionMap,
  });

  const { data: aspectRatiosData } = useQuery({
    queryKey: ['aspectRatios'],
    queryFn: getAspectRatioMap,
  });

  const settingsMutation = useMutation({
    mutationFn: (settings: { resolution?: string; aspect_ratio?: string; clip_preview?: ClipPreview }) =>
      updateProjectSettings(metadata.project_id, settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', metadata.project_id] });
      queryClient.invalidateQueries({ queryKey: ['projectMetadata', metadata.project_id] });
    },
  });

  // Only poll while this project actually has a process running. Previously
  // this refetched every 2s for as long as the page was open.
  const isActive = activeProcesses.some((processId) => processId.startsWith(`${metadata.project_id}_`));
  const isClipperRunning = activeProcesses.includes(`${metadata.project_id}_clipper`);

  const { data: allStatuses } = useQuery({
    queryKey: ['executionStatus', metadata.project_id],
    queryFn: () => getExecutionStatus(metadata.project_id),
    refetchInterval: isActive ? 1000 : (false as const),
  });

  // The metadata itself is already polled by App while the project is active;
  // a second query on its own key just doubled the requests and let the two
  // copies drift apart mid-run.
  const displayMetadata = metadata;

  // execution_status carries a `progress` object alongside the per-step
  // strings, which is the only per-clip feedback available during a run.
  const clipProgress = allStatuses?.progress as unknown as
    | { generated: number; total: number }
    | undefined;

  const sourceUrl = displayMetadata.files?.original_file
    ? getSourceVideoUrl(displayMetadata.project_id, displayMetadata.files.original_file)
    : null;

  // Clips are previewed from the source before anything is cut, so the preview
  // has to box itself to whatever these two settings resolve to.
  const previewAspectRatio = targetAspectRatio(displayMetadata.settings, aspectRatiosData, resolutionsData);

  // These option lists arrive from their own queries, so on first paint — and
  // for good if the request fails — the map is empty. A select whose value has
  // no matching option displays the first one instead, which told the user the
  // project was on "keep original" when it was not. The stored value is always
  // offered, whether or not the map has caught up.
  const optionsFor = (map: Record<string, string> | undefined, current: string) => {
    const keys = Object.keys(map ?? {});
    return keys.includes(current) || current === 'keep original' ? keys : [current, ...keys];
  };

  const highlightCount = displayMetadata.highlights?.length ?? 0;
  const hasHighlights = highlightCount > 0;
  const renderedCount = (displayMetadata.highlights ?? []).filter((h: any) => h.is_clip_generated).length;

  const currentResolution = displayMetadata.settings?.resolution || 'keep original';
  const currentAspectRatio = displayMetadata.settings?.aspect_ratio || 'keep original';
  // What a clip shows while it sits still, for every clip in this project: its
  // thumbnail, or the video frame under it.
  const currentClipPreview: ClipPreview =
    displayMetadata.settings?.clip_preview === 'video' ? 'video' : 'thumbnail';

  // Every highlight is a card from the moment the highlights step finishes;
  // the clipper only swaps a preview for a rendered file.
  //
  // Memoised because this page polls twice a second while a step runs. Rebuilt
  // inline, the array and every object in it were new identities on each tick,
  // which defeated any memo on the cards downstream.
  const clips = React.useMemo(
    () =>
      (displayMetadata.highlights ?? []).map((h: any, index: number) => ({
        index,
        filename: h.generated_clip_filename ?? null,
        isRendered: !!h.is_clip_generated,
        // Whether the file already carries captions decides whether the card
        // draws them over it or leaves them to the pixels.
        captionsBurned: !!h.captions_burned,
        // Same for the overlay title, which is burned on its own schedule: a
        // clip cut before it was written carries the words and not the title.
        overlayBurned: !!h.overlay_burned,
        // A re-cut clip keeps its filename, so the card needs this to stop
        // playing the copy the browser already has.
        renderedAt: h.rendered_at ?? null,
        // A published clip is not republished by accident: the card says it is
        // live, and its upload button asks before adding a second video.
        youtubeUrl: h.youtube_url ?? null,
        youtubeVideoId: h.youtube_video_id ?? null,
        // What a finished upload job is judged against: it leaves
        // /active_processes whether or not it published anything.
        uploadedAt: h.uploaded_at ?? null,
        original_start: h.start,
        original_end: h.end,
        // The card is named by what the clip would be published as; the hook is
        // what it falls back to before the video meta step has run.
        title: h.video_title_for_youtube_short,
        hook: h.viral_hook_text,
        text: h.highlight_text,
      })),
    [displayMetadata.highlights]
  );

  const steps = (pipelineConfig?.execution_order || []).map((stepName: string) => {
    return {
      name: stepName,
      label: stepLabel(stepName),
      status: (allStatuses?.[stepName] as StepStatus) || 'locked',
      isLlm: pipelineConfig?.steps?.[stepName]?.llm === true,
      // A locked step can now say what is blocking it instead of just that it
      // is blocked. The config already carries this; nothing read it before.
      dependsOn: (pipelineConfig?.steps?.[stepName]?.depends_on ?? []).map(stepLabel),
    };
  });

  const renderMetadata = () => {
    const { highlights } = displayMetadata;
    // Prompt-defined tasks have no bespoke view, so they are rendered
    // generically alongside the highlights.
    const llmOutputs = (
      <LlmOutputs projectId={displayMetadata.project_id} outputs={displayMetadata.llm_outputs || {}} />
    );

    if (!highlights || highlights.length === 0) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          {/* An empty panel should say which step fills it, not just that it
              is empty. */}
          <div style={{ padding: 'var(--space-md)', color: 'var(--text-muted)' }}>
            No highlights yet. Run the Highlights step to pick out the moments worth clipping.
          </div>
          {llmOutputs}
        </div>
      );
    }

    // A re-run can return fewer highlights than the last one, leaving the
    // index pointing past the end of the new list.
    const index = Math.min(currentIndex, highlights.length - 1);
    const h = highlights[index];
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-main)' }}>Content Highlights</h2>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{index + 1} / {highlights.length}</span>
            <Button
              variant="ghost"
              onClick={() => { setSwapDirection(-1); setCurrentIndex(Math.max(0, index - 1)); }}
              disabled={index === 0}
            >
              Prev
            </Button>
            <Button
              variant="ghost"
              onClick={() => { setSwapDirection(1); setCurrentIndex(Math.min(highlights.length - 1, index + 1)); }}
              disabled={index === highlights.length - 1}
            >
              Next
            </Button>
          </div>
        </div>

        {/* Prev/Next replaces the whole panel, so the swap has to be announced.
            The announcement is this one sentence rather than the panel itself:
            an aria-live region around the panel re-read the hook, the quote and
            all three social posts on every press, and again on every background
            metadata refresh. */}
        <p className="visually-hidden" role="status" aria-live="polite">
          Highlight {index + 1} of {highlights.length}
          {h.viral_hook_text ? `: ${h.viral_hook_text}` : ''}
        </p>

        <div
          // Keyed on the index so React remounts the panel and the entrance
          // replays on every page, rather than only the first.
          key={index}
          className="highlight-swap"
          style={{
            ['--swap-from' as string]: swapDirection > 0 ? '12px' : '-12px',
            padding: 'var(--space-md)',
            border: 'var(--border)',
            background: 'var(--bg)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-sm)',
            // Model output is arbitrary text: a URL or an unspaced CJK run has
            // no break opportunity and would otherwise widen the whole page.
            overflowWrap: 'anywhere',
          }}
        >
          <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: 'var(--text-accent)' }}>
            {h.viral_hook_text || `Highlight ${index + 1}`}
          </div>
          {h.highlight_text && <div style={{ fontSize: '0.95rem', color: 'var(--text-main)' }}>"{h.highlight_text}"</div>}

          {/* Flat columns under a rule, not boxes. These sit inside the
              bordered highlight panel, so giving each one its own border made
              a card inside a card — the one nesting DESIGN.md rules out. */}
          <div className="social-grid" style={{ marginTop: 'var(--space-sm)' }}>
            {[
              { label: 'X Post', text: h.video_description_for_x },
              { label: 'Reddit', text: h.video_description_for_reddit },
              { label: 'LinkedIn', text: h.video_description_for_linkedin },
            ].map((social) => (
              <div
                key={social.label}
                style={{
                  borderTop: 'var(--border)',
                  paddingTop: 'var(--space-sm)',
                  minWidth: 0,
                }}
              >
                <div style={{ fontSize: '0.65rem', fontWeight: 900, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 'var(--space-sm)' }}>{social.label}</div>
                <div style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>
                  {social.text || <span style={{ color: 'var(--text-muted)' }}>No post for this platform.</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {llmOutputs}
      </div>
    );
  };

  return (
    <div className="project-detail" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="project-layout">
        <div className="project-layout__main">
          {/* The title alone. Everything that used to crowd it — the two output
              settings, the two page actions — is in the options bar below,
              along with the two dialogs that were down in the aside. */}
          <div style={{ minWidth: 0, marginBottom: 'var(--space-md)' }}>
            {/* Project names come from filenames, so a 200-character name with
                no spaces is entirely possible. */}
            <h1 style={{ fontSize: 'clamp(2rem, 5vw, 3rem)', margin: 0, overflowWrap: 'anywhere' }}>{displayMetadata.name}</h1>
            {/* The project id used to sit here. It is already in the address
                bar, so printing it again spent the second-most prominent
                line on the page on a value nobody reads. These are the facts
                the page is actually about. */}
            <p style={{ margin: 'var(--space-xs) 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
              {highlightCount === 1 ? '1 highlight' : `${highlightCount} highlights`}
              {highlightCount > 0 && ` · ${renderedCount} rendered`}
            </p>
          </div>

          {/* Every project-level option, in one row and in the order you meet
              them: what the clipper renders at, what it burns in, what the
              upload says, then what you can inspect or take away. */}
          <div className="options-bar">
            <div className="options-bar__group">
              <span className="options-bar__setting">
                <label htmlFor={resolutionId}>Resolution:</label>
                <select
                  id={resolutionId}
                  value={currentResolution}
                  disabled={settingsMutation.isPending}
                  onChange={(e) => settingsMutation.mutate({ resolution: e.target.value })}
                  style={{ fontSize: '0.8rem', fontWeight: 600, minHeight: '44px', background: 'var(--bg-secondary)', color: 'var(--text-main)', border: '2px solid var(--border-color)', padding: '2px var(--space-sm)' }}
                >
                  <option value="keep original">Keep original</option>
                  {/* Not uppercased: these are format names, and "1080P"
                      is not how anyone writes 1080p. */}
                  {optionsFor(resolutionsData, currentResolution).map(opt => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              </span>
              <span className="options-bar__setting">
                <label htmlFor={aspectRatioId}>Aspect Ratio:</label>
                <select
                  id={aspectRatioId}
                  value={currentAspectRatio}
                  disabled={settingsMutation.isPending}
                  onChange={(e) => settingsMutation.mutate({ aspect_ratio: e.target.value })}
                  style={{ fontSize: '0.8rem', fontWeight: 600, minHeight: '44px', background: 'var(--bg-secondary)', color: 'var(--text-main)', border: '2px solid var(--border-color)', padding: '2px var(--space-sm)' }}
                >
                  <option value="keep original">Keep original</option>
                  {optionsFor(aspectRatiosData, currentAspectRatio).map(opt => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              </span>
              {/* Not a render setting like the two above — this one changes
                  nothing about the files. It sits with them because it is the
                  third thing that applies to every clip at once, and because
                  it is about the grid directly below. */}
              <span className="options-bar__setting">
                <label htmlFor={clipPreviewId}>Still clips show:</label>
                <select
                  id={clipPreviewId}
                  value={currentClipPreview}
                  disabled={settingsMutation.isPending}
                  onChange={(e) => settingsMutation.mutate({ clip_preview: e.target.value as ClipPreview })}
                  style={{ fontSize: '0.8rem', fontWeight: 600, minHeight: '44px', background: 'var(--bg-secondary)', color: 'var(--text-main)', border: '2px solid var(--border-color)', padding: '2px var(--space-sm)' }}
                >
                  <option value="thumbnail">Thumbnail</option>
                  <option value="video">Video frame</option>
                </select>
              </span>
            </div>

            {/* Text actions, not buttons. Rendered clips are what this page is
                for, so the only things that still look like buttons are the
                ones that make them — the pipeline steps. Delete stays out of
                here entirely; it is at the foot of the page. */}
            <div className="options-bar__group">
              {/* Captions and Description were in the sticky aside, which put
                  two project-wide settings below the fold on a short window and
                  left the reader to discover them by scrolling a column that
                  otherwise holds a video. */}
              <CaptionStyler
                variant="inline"
                projectId={displayMetadata.project_id}
                settings={displayMetadata.settings?.captions}
              />
              <DescriptionPanel
                variant="inline"
                projectId={displayMetadata.project_id}
                settings={displayMetadata.settings?.description}
              />
              <button
                type="button"
                className="text-action"
                onClick={() => setShowMetadata(!showMetadata)}
                aria-expanded={showMetadata}
                aria-controls={metadataPanelId}
              >
                {showMetadata ? 'Hide AI Output' : 'View AI Output'}
              </button>
              {hasHighlights ? (
                // A real download link rather than a button assigning
                // window.location: this restores middle-click, ctrl-click and
                // the filename, and stops the export unloading the app.
                <a
                  className="text-action"
                  href={getMarkerEdlUrl(displayMetadata.project_id)}
                  download
                >
                  Export markers
                </a>
              ) : (
                <span className="text-action" aria-disabled="true">Export markers</span>
              )}
            </div>
          </div>

          {settingsMutation.isError && (
            <p role="alert" style={{ margin: 'var(--space-sm) 0 0 0', fontSize: '0.7rem', color: 'var(--error)' }}>
              Could not save that setting:{' '}
              {settingsMutation.error instanceof Error ? settingsMutation.error.message : 'please try again.'}
            </p>
          )}


          {/* Entrance only, no exit. The alternative — keeping this mounted and
              animating grid-template-rows both ways — would hold the LLM output
              tables (up to 200 rows) in the DOM for the whole session, which is
              the opposite of what the page needs. */}
          {showMetadata && (
            <section
              id={metadataPanelId}
              className="panel-enter"
              style={{ marginBottom: 'var(--space-md)' }}
            >
              {renderMetadata()}
            </section>
          )}

          <section>
            <PipelineController onExecute={onExecuteAction} steps={steps} />
            {isActive && clipProgress && clipProgress.total > 0 && (
              <p
                role="status"
                aria-live="polite"
                style={{ margin: 'var(--space-sm) 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}
              >
                Rendered {clipProgress.generated} of {clipProgress.total} clips
              </p>
            )}
          </section>
        </div>

        <div className="project-layout__aside">
          <div style={{ 
            border: 'var(--border)', 
            backgroundColor: '#000',
            lineHeight: 0 
          }}>
            {sourceUrl && !sourceVideoFailed ? (
              <video
                src={sourceUrl}
                controls
                // Source files run to gigabytes; without this the browser
                // downloads the whole thing on page load.
                preload="metadata"
                aria-label={`Source video for ${displayMetadata.name}`}
                onError={() => setSourceVideoFailed(true)}
                style={{
                  width: '100%',
                  display: 'block'
                }}
              />
            ) : (
              // Paired with the black letterbox behind it, which is deliberate
              // in both themes, so this text can't follow the theme tokens.
              <div role="status" style={{ padding: '2rem', color: '#F9F9F9', textAlign: 'center', fontSize: '0.8rem', lineHeight: 1.4 }}>
                {sourceVideoFailed
                  ? 'The source video could not be played. It may still be uploading, or the file was moved.'
                  : 'No original file available.'}
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ borderBottom: 'var(--border)', margin: 'var(--space-md) 0 0 0' }} />

      <section>
        <ClipManager
          projectId={displayMetadata.project_id}
          clips={clips}
          sourceUrl={sourceUrl}
          aspectRatio={previewAspectRatio}
          clipPreview={currentClipPreview}
          onDeleteClip={onDeleteClip}
          isLoading={isClipperRunning}
        />
      </section>

      {/* The one irreversible action on the page, at the end of it. In the
          header it was the same size as Export and sat next to it. */}
      <div style={{ borderTop: 'var(--border)', paddingTop: 'var(--space-md)', marginTop: 'var(--space-md)' }}>
        <Button variant="danger" onClick={onDeleteProject} style={{ fontSize: '0.8rem' }}>
          Delete project
        </Button>
      </div>

    </div>
        );
        }
;
