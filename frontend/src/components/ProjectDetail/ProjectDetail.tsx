import React, { useId } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PipelineActivity, PipelineController } from '../PipelineController/PipelineController';
import type { StepStatus } from '../PipelineController/PipelineController';
import { ClipManager } from '../ClipManagement/ClipManager';
import {
  getResolutionMap,
  getAspectRatioMap,
  getExecutionStatus,
  getSourceVideoUrl,
  type ClipPreview,
  type Highlight,
  type ProjectMetadata,
  type StepActivity,
} from '../../api';
import { targetAspectRatio } from '../../utils/aspectRatio';
import { stepLabel } from '../../utils/stepLabels';

/**
 * How far into the clips a run has got.
 *
 * Accent, not muted grey: this is the pipeline running, which is what accent
 * means in the step row above it. It is also the only line on the page that
 * changes by itself, and it used to be the same colour as the labels that do
 * not.
 */
const ProgressLine: React.FC<{ progress: { generated: number; total: number } }> = ({ progress }) => (
  <p
    role="status"
    aria-live="polite"
    style={{ margin: 'var(--space-sm) 0 0 0', fontSize: '0.8rem', color: 'var(--text-accent)', fontWeight: 700 }}
  >
    Rendered {progress.generated} of {progress.total} clips
  </p>
);

interface ProjectDetailProps {
  metadata: ProjectMetadata;
  pipelineConfig: {
    execution_order: string[];
    steps?: Record<string, { auto_run?: boolean; llm?: boolean; depends_on?: string[] }>;
  };
  activeProcesses: string[];
  onExecuteAction: (action: 'START' | 'STOP', step: string) => void;
  onDeleteClip: (index: number) => void;
}

export const ProjectDetail: React.FC<ProjectDetailProps> = ({ metadata, pipelineConfig, activeProcesses, onExecuteAction, onDeleteClip }) => {
  const pipelineHeadingId = useId();
  const clipsHeadingId = useId();

  const { data: resolutionsData } = useQuery({
    queryKey: ['resolutions'],
    queryFn: getResolutionMap,
  });

  const { data: aspectRatiosData } = useQuery({
    queryKey: ['aspectRatios'],
    queryFn: getAspectRatioMap,
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

  // Same shape of cast: what each running step is doing, and the backend's own
  // clock to measure it against.
  const activity = allStatuses?.activity as unknown as
    | Record<string, StepActivity>
    | undefined;
  const serverNow = allStatuses?.now as unknown as number | undefined;

  const sourceUrl = displayMetadata.files?.original_file
    ? getSourceVideoUrl(displayMetadata.project_id, displayMetadata.files.original_file)
    : null;

  // Clips are previewed from the source before anything is cut, so the preview
  // has to box itself to whatever these two settings resolve to.
  const previewAspectRatio = targetAspectRatio(displayMetadata.settings, aspectRatiosData, resolutionsData);

  const highlightCount = displayMetadata.highlights?.length ?? 0;
  const hasHighlights = highlightCount > 0;

  // What a clip shows while it sits still, for every clip in this project: its
  // thumbnail, or the video frame under it. Read from the project rather than
  // held here — the control that changes it is in the header now, and this
  // follows the saved value.
  const currentClipPreview: ClipPreview =
    metadata.settings?.clip_preview === 'video' ? 'video' : 'thumbnail';

  // Every highlight is a card from the moment the highlights step finishes;
  // the clipper only swaps a preview for a rendered file.
  //
  // Memoised because this page polls twice a second while a step runs. Rebuilt
  // inline, the array and every object in it were new identities on each tick,
  // which defeated any memo on the cards downstream.
  const clips = React.useMemo(
    () =>
      (displayMetadata.highlights ?? []).map((h: Highlight, index: number) => ({
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
        // Defaulted, not passed through: `highlight_text` is absent until the
        // highlights step has written it, and the card's type promises a
        // string. `any` on this map hid the mismatch.
        text: h.highlight_text ?? '',
      })),
    [displayMetadata.highlights]
  );

  // Memoised for the same reason `clips` is: this page rebuilds twice a second
  // while a step runs, and an array rebuilt inline is a new prop identity on
  // every tick — which is a `React.memo` on the pipeline row that can never
  // hold. The status strings are what actually change during a run, and they
  // change perhaps four times over a whole pipeline.
  //
  // Keyed on the statuses themselves rather than on the object that carries
  // them: `execution_status` also carries the per-clip `progress` counter,
  // which ticks on every single poll, so depending on the query object would
  // rebuild this list forty times for a run in which the statuses changed
  // three times.
  const statusKey = (pipelineConfig?.execution_order || [])
    .map((stepName) => allStatuses?.[stepName] ?? 'locked')
    .join('|');

  const steps = React.useMemo(
    () =>
      (pipelineConfig?.execution_order || []).map((stepName: string) => ({
        name: stepName,
        label: stepLabel(stepName),
        status: (allStatuses?.[stepName] as StepStatus) || 'locked',
        isLlm: pipelineConfig?.steps?.[stepName]?.llm === true,
        // A locked step can now say what is blocking it instead of just that it
        // is blocked. The config already carries this; nothing read it before.
        dependsOn: (pipelineConfig?.steps?.[stepName]?.depends_on ?? []).map(stepLabel),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- statusKey is
    // exactly the part of allStatuses this reads; see above.
    [pipelineConfig, statusKey]
  );

  return (
    <div className="project-detail">
      {/* The title is not painted, because it is already on the page.
          ------------------------------------------------------------------
          The breadcrumb directly above renders HOME / PROJECTS / <name>, in
          accent, bold, carrying `aria-current="page"`. The h1 under it printed
          the same filename again, larger, thirty pixels lower — two lines of
          heading plus a facts line, some sixty pixels of page, to say a thing
          the page had already said.

          It stays as a heading because the document needs one and a screen
          reader navigates by it; it just stops being drawn twice. The facts it
          used to sit above move into the row of triggers below, which was
          already there and already had the room. */}
      <h1 className="visually-hidden">{displayMetadata.name}</h1>

      {/* Two shapes, one page.
          ------------------------------------------------------------------
          A project with nothing in it is not the same page as a project with
          forty clips in it, and it used to be laid out as though it were.

          With no highlights there is nothing to review, so the pipeline is the
          page and it leads at full size.

          Once there are clips the pipeline has done its job. It runs once —
          and then it is a tool you reach for on the rare occasion you re-cut
          something, which is exactly what the settings beside it are. So it
          folds into the same row and takes no height at all until it is asked
          for, or until it has something to say. Shrinking it was not enough:
          a strip is still a permanent band across a page about clips. */}
      {!hasHighlights && (
        <section aria-labelledby={pipelineHeadingId}>
          <h2 id={pipelineHeadingId} className="visually-hidden">Pipeline</h2>
          <PipelineController onExecute={onExecuteAction} steps={steps} prominence="lead" />
          <PipelineActivity steps={steps} activity={activity} now={serverNow} />
        </section>
      )}

      {/* What the page is for. The source video used to sit beside all of this
          in a sticky 400px column — the one video on the page nobody needs to
          watch, holding the fold against the clips cut out of it. The grid
          still previews from the source; it just no longer plays it twice. */}
      <section aria-labelledby={clipsHeadingId} className="project-clips">
        <h2 id={clipsHeadingId} className="visually-hidden">Clips</h2>
        {/* Counts clips, so it reads above the clips rather than inside a
            pipeline menu in the header. */}
        {isActive && clipProgress && clipProgress.total > 0 && <ProgressLine progress={clipProgress} />}
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

    </div>
  );
};
