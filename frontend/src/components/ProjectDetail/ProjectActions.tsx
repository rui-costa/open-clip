import React, { useEffect, useId, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { PipelineController } from '../PipelineController/PipelineController';
import type { StepStatus } from '../PipelineController/PipelineController';
import { ProjectSettingsMenu } from './ProjectSettingsMenu';
import { HighlightPanel } from './HighlightPanel';
import {
  downloadMarkerEdl,
  getExecutionStatus,
  getMarkerEdlUrl,
  type ProjectMetadata,
} from '../../api';
import { stepLabel } from '../../utils/stepLabels';

/** An LLM outputs map that is the same object every render, so a memo can hold. */
const NO_LLM_OUTPUTS: Record<string, unknown> = {};

interface ProjectActionsProps {
  metadata: ProjectMetadata;
  pipelineConfig: {
    execution_order: string[];
    steps?: Record<string, { auto_run?: boolean; llm?: boolean; depends_on?: string[] }>;
  };
  activeProcesses: string[];
  onExecuteAction: (action: 'START' | 'STOP', step: string) => void;
  onDeleteProject: () => void;
}

/**
 * What you can do to the project you are looking at, in the bar at the top.
 *
 * These three used to be spread down the page — the pipeline as a band across
 * it, the export in a row of settings, delete alone at the foot. They have
 * nothing in common with the settings they sat among and everything in common
 * with each other: each one acts on the whole project rather than on anything
 * you can see, and none of them is what the page is about. The page is about
 * the clips.
 *
 * Rendered into the primary bar, so it is chrome, and only for a project route
 * — a Delete button that outlived the thing it deletes is worse than no button
 * at all.
 */
export const ProjectActions: React.FC<ProjectActionsProps> = ({
  metadata,
  pipelineConfig,
  activeProcesses,
  onExecuteAction,
  onDeleteProject,
}) => {
  // One at a time: two panels hanging over the page from the same bar would
  // overlap each other.
  const [openMenu, setOpenMenu] = useState<'pipeline' | 'settings' | 'writing' | null>(null);
  // Which highlight the writing menu is showing, and which way the last page
  // went so the incoming panel enters from that side.
  const [writingIndex, setWritingIndex] = useState(0);
  const [swapDirection, setSwapDirection] = useState<1 | -1>(1);
  const pipelineMenuId = useId();
  const settingsMenuId = useId();
  const writingMenuId = useId();
  const exportErrorId = useId();
  const containerRef = useRef<HTMLDivElement>(null);

  const projectId = metadata.project_id;
  const hasHighlights = (metadata.highlights?.length ?? 0) > 0;
  const isPipelineOpen = openMenu === 'pipeline';

  const isActive = activeProcesses.some((processId) => processId.startsWith(`${projectId}_`));

  // The same query key the page uses, so this shares its cache and its poll
  // rather than opening a second one.
  const { data: allStatuses } = useQuery({
    queryKey: ['executionStatus', projectId],
    queryFn: () => getExecutionStatus(projectId),
    refetchInterval: isActive ? 1000 : (false as const),
  });

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
        dependsOn: (pipelineConfig?.steps?.[stepName]?.depends_on ?? []).map(stepLabel),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- statusKey is
    // exactly the part of allStatuses this reads.
    [pipelineConfig, statusKey]
  );

  const anyRunning = steps.some((step) => step.status === 'running');
  const anyFailed = steps.some((step) => step.status === 'error');
  const allDone =
    steps.length > 0 && steps.every((step) => step.status === 'completed' || step.status === 'executed');

  // Folded away is not the same as hidden: whatever the row would have said
  // about itself, the trigger says.
  const badge = anyFailed
    ? { label: 'failed', style: { background: 'var(--error)', color: 'var(--bg)' } }
    : anyRunning
      ? { label: 'running', style: { background: 'var(--accent)', color: 'var(--bg)' } }
      : allDone
        ? { label: 'done', style: { background: 'var(--success)', color: 'var(--on-success)' } }
        : null;

  // Opened for you when the pipeline starts doing something or fails — the two
  // moments it is worth the room. Set rather than derived, so closing it again
  // is a choice this respects.
  useEffect(() => {
    if (anyRunning || anyFailed) setOpenMenu('pipeline');
  }, [anyRunning, anyFailed]);

  // A menu in the header hangs over the page, so it has to close the way a
  // menu closes: on Escape, and on a press anywhere else.
  useEffect(() => {
    if (!openMenu) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenMenu(null);
    };
    const onPointerDown = (event: PointerEvent) => {
      // The caption and description dialogs are portalled to the body, so a
      // press inside one is outside this container and would otherwise close
      // the menu that opened it.
      const target = event.target as Node;
      if (containerRef.current?.contains(target)) return;
      if ((target as HTMLElement).closest?.('[role="dialog"]')) return;
      setOpenMenu(null);
    };
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [openMenu]);

  // Stable, so the memo on the panel is not undone by the one prop that would
  // otherwise be new on every render.
  const handlePage = React.useCallback((direction: 1 | -1, nextIndex: number) => {
    setSwapDirection(direction);
    setWritingIndex(nextIndex);
  }, []);

  const exportMutation = useMutation({
    mutationFn: () => downloadMarkerEdl(projectId, metadata.name),
  });

  return (
    <div className="project-actions" ref={containerRef}>
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          className="nav-action"
          onClick={() => setOpenMenu(isPipelineOpen ? null : 'pipeline')}
          aria-expanded={isPipelineOpen}
          aria-controls={pipelineMenuId}
        >
          Pipeline
          {badge && (
            <span className="status-badge" style={badge.style}>
              {badge.label}
            </span>
          )}
        </button>

        {isPipelineOpen && (
          <div id={pipelineMenuId} className="project-actions__menu menu-enter">
            <PipelineController onExecute={onExecuteAction} steps={steps} prominence="compact" />
          </div>
        )}
      </div>

      <div style={{ position: 'relative' }}>
        <button
          type="button"
          className="nav-action"
          onClick={() => setOpenMenu(openMenu === 'settings' ? null : 'settings')}
          aria-expanded={openMenu === 'settings'}
          aria-controls={settingsMenuId}
        >
          {/* Not "Settings": the primary nav beside this one already has a
              button by that name, for the application's own settings. Two
              controls with the same accessible name in the same bar is a
              guess for everybody and a coin toss for a screen reader. */}
          Project settings
        </button>

        {openMenu === 'settings' && (
          <div id={settingsMenuId} className="project-actions__menu menu-enter">
            <ProjectSettingsMenu metadata={metadata} />
          </div>
        )}
      </div>

      <div style={{ position: 'relative' }}>
        <button
          type="button"
          className="nav-action"
          onClick={() => setOpenMenu(openMenu === 'writing' ? null : 'writing')}
          aria-expanded={openMenu === 'writing'}
          aria-controls={writingMenuId}
        >
          {/* "View AI Output" named where the text came from, and opened a
              panel headed "Content Highlights" — two names for one thing,
              neither of them what it is. It is the writing. */}
          Writing
        </button>

        {openMenu === 'writing' && (
          <div
            id={writingMenuId}
            className="project-actions__menu project-actions__menu--wide menu-enter"
          >
            <HighlightPanel
              projectId={projectId}
              highlights={metadata.highlights}
              llmOutputs={metadata.llm_outputs ?? NO_LLM_OUTPUTS}
              index={writingIndex}
              swapDirection={swapDirection}
              onPage={handlePage}
            />
          </div>
        )}
      </div>

      {hasHighlights ? (
        // Still a real link, so middle-click, ctrl-click and right-click-save
        // behave the way they look like they will — but a plain left click is
        // handled in JS, because following this href is a cross-origin
        // navigation that lands on the backend's JSON error page whenever the
        // export fails.
        <a
          className="nav-action"
          href={getMarkerEdlUrl(projectId)}
          download
          aria-busy={exportMutation.isPending}
          aria-describedby={exportMutation.isError ? exportErrorId : undefined}
          onClick={(e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
            e.preventDefault();
            // An impatient second click would otherwise start a second export
            // and hand the user two copies of the same file.
            if (exportMutation.isPending) return;
            exportMutation.mutate();
          }}
        >
          {exportMutation.isPending ? 'Exporting…' : 'Export'}
        </a>
      ) : (
        // A real disabled button, not a span wearing `aria-disabled`. A span
        // has no role for the state to attach to, so a screen reader read this
        // as a stray phrase and the keyboard never reached it at all.
        <button type="button" className="nav-action" disabled>
          Export — run Highlights first
        </button>
      )}

      {/* Danger colouring, and a confirmation dialog behind it. This is the one
          irreversible action in the application and it now sits two buttons
          from Projects and Settings, which is the price of putting it where
          the other project actions are. */}
      <button type="button" className="nav-action nav-action--danger" onClick={onDeleteProject}>
        Delete
      </button>

      {exportMutation.isError && (
        <p id={exportErrorId} role="alert" className="project-actions__error">
          Could not export the markers:{' '}
          {exportMutation.error instanceof Error ? exportMutation.error.message : 'please try again.'}
        </p>
      )}
    </div>
  );
};
