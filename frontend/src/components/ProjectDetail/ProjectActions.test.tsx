import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectActions } from './ProjectActions';
import type { ProjectMetadata } from '../../api';

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return {
    ...actual,
    getExecutionStatus: vi.fn(async () => ({})),
    downloadMarkerEdl: vi.fn(async () => undefined),
    getResolutionMap: vi.fn(async () => ({ '1080p': '1920x1080', '720p': '1280x720' })),
    getAspectRatioMap: vi.fn(async () => ({ '16:9': '16:9', '9:16': '9:16' })),
    updateProjectSettings: vi.fn(async () => ({ status: 'ok' })),
    getCaptionStyles: vi.fn(async () => ({
      karaoke_pop: { label: 'Karaoke Pop', description: 'words pop', font_size_pct: 7, position_pct: 78 },
      clean_lines: { label: 'Clean Lines', description: 'plain blocks', font_size_pct: 4.8, position_pct: 86 },
    })),
  };
});

const pipelineConfig = {
  execution_order: ['transcription', 'clipper'],
  steps: {} as Record<string, { llm?: boolean; depends_on?: string[] }>,
};

const highlight = (text: string) => ({
  start: 0,
  end: 1,
  highlight_text: text,
  viral_hook_text: `${text} hook`,
  video_description_for_x: 'x',
  video_description_for_reddit: 'reddit',
  video_description_for_linkedin: 'linkedin',
});

const metadata = (highlights: unknown[] = [{ start: 0, end: 1 }]): ProjectMetadata => ({
  project_id: 'p1',
  name: 'Test Project',
  created_at: new Date().toISOString(),
  highlights: highlights as never[],
  settings: { resolution: '1080p', aspect_ratio: '16:9' },
  files: { original_file: 'original.mp4' },
});

const renderActions = (props: Partial<React.ComponentProps<typeof ProjectActions>> = {}) => {
  const onDeleteProject = props.onDeleteProject ?? vi.fn();
  const view = render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ProjectActions
        metadata={metadata()}
        pipelineConfig={pipelineConfig}
        activeProcesses={[]}
        onExecuteAction={vi.fn()}
        {...props}
        onDeleteProject={onDeleteProject}
      />
    </QueryClientProvider>
  );
  return { ...view, onDeleteProject };
};

// The pipeline, the export and delete all act on the whole project rather than
// on anything in view, so they are chrome. These tests moved here with them.
describe('ProjectActions', () => {
  beforeEach(() => vi.clearAllMocks());

  describe('pipeline', () => {
    it('keeps the pipeline behind its trigger', () => {
      renderActions();

      expect(screen.queryByRole('button', { name: /Run full pipeline/i })).toBeNull();

      const trigger = screen.getByRole('button', { name: /^Pipeline/i });
      expect(trigger.getAttribute('aria-expanded')).toBe('false');
      fireEvent.click(trigger);

      expect(screen.getByRole('button', { name: /Run full pipeline/i })).toBeDefined();
      expect(trigger.getAttribute('aria-expanded')).toBe('true');
    });

    // Folded away is not the same as hidden.
    it('carries the pipeline state on the trigger while it is folded', async () => {
      const { getExecutionStatus } = await import('../../api');
      vi.mocked(getExecutionStatus).mockResolvedValue({ clipper: 'error' } as never);
      renderActions();

      const badge = await screen.findByText('failed');
      expect(badge.className).toContain('status-badge');
      expect(badge.style.background).toBe('var(--error)');
    });

    // The state the user is in when they close the panel and come back
    // tomorrow. "done" there is the whole bug: one draft filed of twenty, and
    // the bar saying the job is finished.
    it('says partial on the trigger for a step that only half worked', async () => {
      const { getExecutionStatus } = await import('../../api');
      vi.mocked(getExecutionStatus).mockResolvedValue({
        transcription: 'completed',
        clipper: 'partial',
      } as never);
      renderActions();

      const badge = await screen.findByText('partial');
      expect(badge.style.background).toBe('var(--warning)');
      expect(screen.queryByText('done')).toBeNull();
    });

    it('opens itself when a step starts running, and lets you close it again', async () => {
      const { getExecutionStatus } = await import('../../api');
      vi.mocked(getExecutionStatus).mockResolvedValue({ clipper: 'running' } as never);
      renderActions({ activeProcesses: ['p1_clipper'] });

      const trigger = await screen.findByRole('button', { name: /^Pipeline/i });
      await waitFor(() => expect(trigger.getAttribute('aria-expanded')).toBe('true'));

      // Opened for you, not forced on you.
      fireEvent.click(trigger);
      expect(trigger.getAttribute('aria-expanded')).toBe('false');
    });

    // It hangs over the page from the header, so it closes the way a menu does.
    it('closes on escape and on a press outside it', () => {
      renderActions();

      fireEvent.click(screen.getByRole('button', { name: /^Pipeline/i }));
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(screen.queryByRole('button', { name: /Run full pipeline/i })).toBeNull();

      fireEvent.click(screen.getByRole('button', { name: /^Pipeline/i }));
      fireEvent.pointerDown(document.body);
      expect(screen.queryByRole('button', { name: /Run full pipeline/i })).toBeNull();
    });
  });

  describe('project settings', () => {
    it('keeps the settings out of the way until they are asked for', () => {
      renderActions();

      expect(screen.queryByLabelText(/Resolution/i)).toBeNull();

      const trigger = screen.getByRole('button', { name: /Project settings/i });
      expect(trigger.getAttribute('aria-expanded')).toBe('false');
      fireEvent.click(trigger);

      expect(screen.getByLabelText(/Resolution/i)).toBeDefined();
    });

    // The primary nav beside this one already has a SETTINGS button, for the
    // application's own settings. Two controls with the same accessible name
    // in one bar is a coin toss for a screen reader.
    it('does not share a name with the application settings', () => {
      renderActions();

      expect(screen.getByRole('button', { name: /Project settings/i })).toBeDefined();
      expect(screen.queryByRole('button', { name: /^Settings$/i })).toBeNull();
    });

    // The caption and description dialogs are portalled to the body, so a
    // press inside one lands outside this menu's container.
    it('stays open when a dialog it opened is pressed', async () => {
      renderActions();
      fireEvent.click(screen.getByRole('button', { name: /Project settings/i }));

      fireEvent.click(await screen.findByRole('button', { name: /Captions/i }));
      const dialog = screen.getByRole('dialog');
      fireEvent.pointerDown(dialog);

      expect(screen.getByLabelText(/Resolution/i)).toBeDefined();
    });

    it('opens only one menu at a time', () => {
      renderActions();

      fireEvent.click(screen.getByRole('button', { name: /^Pipeline/i }));
      expect(screen.getByRole('button', { name: /Run full pipeline/i })).toBeDefined();

      fireEvent.click(screen.getByRole('button', { name: /Project settings/i }));
      expect(screen.queryByRole('button', { name: /Run full pipeline/i })).toBeNull();
      expect(screen.getByLabelText(/Resolution/i)).toBeDefined();
    });
  });

  describe('writing', () => {
    it('keeps the writing behind its trigger', () => {
      renderActions({ metadata: metadata([highlight('one')]) });

      expect(screen.queryByText(/Content Highlights/i)).toBeNull();

      const trigger = screen.getByRole('button', { name: /^Writing$/i });
      fireEvent.click(trigger);

      expect(screen.getByText(/Content Highlights/i)).toBeDefined();
      expect(trigger.getAttribute('aria-expanded')).toBe('true');
    });

    // A re-run can return fewer highlights than the last one, leaving the index
    // pointing past the end of the new list.
    it('survives a re-run that returns fewer highlights than are paged past', () => {
      const { rerender } = renderActions({
        metadata: metadata([highlight('one'), highlight('two'), highlight('three')]),
      });

      fireEvent.click(screen.getByRole('button', { name: /^Writing$/i }));
      fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
      fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
      expect(screen.getByText('3 / 3')).toBeDefined();

      rerender(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <ProjectActions
            metadata={metadata([highlight('only one left')])}
            pipelineConfig={pipelineConfig}
            activeProcesses={[]}
            onExecuteAction={vi.fn()}
            onDeleteProject={vi.fn()}
          />
        </QueryClientProvider>
      );

      expect(screen.getByText('1 / 1')).toBeDefined();
      expect(screen.getByText('"only one left"')).toBeDefined();
    });
  });

  describe('export', () => {
    // Exporting markers for a project with no highlights would hand the editor
    // an empty EDL, so it is not offered until there is something in it — as a
    // real disabled button, not a span wearing aria-disabled.
    it('does not offer a marker export before any highlights exist', () => {
      renderActions({ metadata: metadata([]) });

      expect(screen.queryByRole('link', { name: /Export/i })).toBeNull();
      const disabled = screen.getByRole('button', { name: /Export/i }) as HTMLButtonElement;
      expect(disabled.disabled).toBe(true);
      // Disabled is not an answer on its own; the label carries the reason.
      expect(disabled.textContent).toMatch(/run Highlights first/i);
    });

    it('offers the marker export as a real download link once highlights exist', () => {
      renderActions();

      expect(screen.getByRole('link', { name: /^Export$/i }).hasAttribute('download')).toBe(true);
    });

    // Following the href is a cross-origin navigation, so a failed export used
    // to replace the whole application with the backend's JSON error page.
    it('reports a failed marker export without leaving the page', async () => {
      const { downloadMarkerEdl } = await import('../../api');
      vi.mocked(downloadMarkerEdl).mockRejectedValueOnce(new Error('bad timecode'));
      renderActions();

      fireEvent.click(screen.getByRole('link', { name: /^Export$/i }));

      const alert = await screen.findByRole('alert');
      expect(alert.textContent).toMatch(/Could not export the markers/i);
      expect(alert.textContent).toMatch(/bad timecode/i);
    });

    // A modifier click is the browser's, not ours.
    it('leaves modified clicks on the export to the browser', async () => {
      const { downloadMarkerEdl } = await import('../../api');
      renderActions();

      fireEvent.click(screen.getByRole('link', { name: /^Export$/i }), { ctrlKey: true });

      expect(vi.mocked(downloadMarkerEdl)).not.toHaveBeenCalled();
    });
  });

  describe('delete', () => {
    it('asks the application to confirm rather than deleting on the press', () => {
      const { onDeleteProject } = renderActions();

      fireEvent.click(screen.getByRole('button', { name: /^Delete$/i }));

      // The handler opens the confirmation dialog; nothing is destroyed here.
      expect(onDeleteProject).toHaveBeenCalledTimes(1);
    });

    // It sits two buttons from Projects and Settings now, so it has to keep
    // saying what it is.
    it('stays marked as the destructive one', () => {
      renderActions();

      expect(screen.getByRole('button', { name: /^Delete$/i }).className).toContain('nav-action--danger');
    });
  });
});
