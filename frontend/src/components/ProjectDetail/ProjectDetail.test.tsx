import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ProjectDetail } from './ProjectDetail';
import type { ProjectMetadata } from '../../api';

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return {
    ...actual,
    getResolutionMap: vi.fn(async () => ({ '1080p': '1920x1080', '720p': '1280x720' })),
    getAspectRatioMap: vi.fn(async () => ({ '16:9': '16:9', '9:16': '9:16' })),
    getExecutionStatus: vi.fn(async () => ({})),
    updateProjectSettings: vi.fn(async () => ({ status: 'ok' })),
    getCaptionStyles: vi.fn(async () => ({
      karaoke_pop: { label: 'Karaoke Pop', description: 'words pop', font_size_pct: 7, position_pct: 78 },
      clean_lines: { label: 'Clean Lines', description: 'plain blocks', font_size_pct: 4.8, position_pct: 86 },
    })),
    getClipCaptions: vi.fn(async () => ({ enabled: false, style: {}, duration: 0, cues: [] })),
    getActiveProcesses: vi.fn(async () => []),
    getClipThumbnail: vi.fn(async () => ({
      settings: {
        frame_time: 0,
        show_captions: false,
        show_overlay: true,
        extra: null,
        generated_filename: null,
        generated_at: null,
      },
      title: null,
      title_font: null,
      duration: 1,
      exists: false,
    })),
  };
});

const highlight = (text: string, clip?: string) => ({
  highlight_text: text,
  viral_hook_text: `${text} hook`,
  video_description_for_x: 'x',
  video_description_for_reddit: 'reddit',
  video_description_for_linkedin: 'linkedin',
  start: 0,
  end: 1,
  is_clip_generated: Boolean(clip),
  generated_clip_filename: clip,
});

const metadata = (highlights: unknown[]): ProjectMetadata => ({
  project_id: 'p1',
  name: 'Test Project',
  created_at: new Date().toISOString(),
  // No `clips` field: cut clips are the highlights carrying
  // `is_clip_generated`, which is what ProjectMetadata declares.
  highlights: highlights as any[],
  settings: { resolution: '1080p', aspect_ratio: '16:9' },
  files: { original_file: 'original.mp4' },
});

const renderDetail = (props: Partial<React.ComponentProps<typeof ProjectDetail>> = {}) => {
  const onExecuteAction = props.onExecuteAction ?? vi.fn();
  const view = render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <ProjectDetail
          metadata={metadata([highlight('one'), highlight('two'), highlight('three')])}
          pipelineConfig={{ execution_order: ['clipper'], steps: {} }}
          activeProcesses={[]}
          onExecuteAction={onExecuteAction}
          onDeleteClip={vi.fn()}
          onDeleteProject={vi.fn()}
          {...props}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { ...view, onExecuteAction };
};

describe('ProjectDetail', () => {
  beforeEach(() => vi.clearAllMocks());

  it('names both video settings controls for assistive tech', () => {
    renderDetail();

    expect(screen.getByLabelText(/Resolution/i)).toBeDefined();
    expect(screen.getByLabelText(/Aspect Ratio/i)).toBeDefined();
  });

  // The header's "Render All Clips" button is gone: the Clips step already
  // started the same job, and its locked state — driven by depends_on —
  // enforces "no highlights, no render" without a second control.
  it('leaves rendering to the pipeline row', () => {
    renderDetail();

    expect(screen.queryByRole('button', { name: /Render All Clips/i })).toBeNull();
  });

  // Exporting markers for a project with no highlights would hand the editor
  // an empty EDL, so the link is not offered until there is something in it.
  it('does not offer a marker export before any highlights exist', () => {
    renderDetail({ metadata: metadata([]) });

    expect(screen.queryByRole('link', { name: /Export markers/i })).toBeNull();
    expect(screen.getByText(/Export markers/i).getAttribute('aria-disabled')).toBe('true');
  });

  // The picture itself is not made until a clip is published; the grid draws
  // its thumbnails, so there is nothing here to render in advance.
  it('offers a project-wide choice between the thumbnail and the footage', () => {
    renderDetail();

    const control = screen.getByLabelText(/Still clips show/i) as HTMLSelectElement;
    expect(control.value).toBe('thumbnail');
  });

  it('offers the marker export as a real download link once highlights exist', () => {
    renderDetail();

    const link = screen.getByRole('link', { name: /Export markers/i });
    expect(link.hasAttribute('download')).toBe(true);
  });

  it('leads with what the project actually contains', () => {
    renderDetail();

    expect(screen.getByText(/3 highlights/i)).toBeDefined();
  });

  it('survives a re-run that returns fewer highlights than are paged past', () => {
    const { rerender } = renderDetail();

    fireEvent.click(screen.getByRole('button', { name: /View AI Output/i }));
    fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
    expect(screen.getByText('3 / 3')).toBeDefined();

    rerender(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <ProjectDetail
            metadata={metadata([highlight('only one left')])}
            pipelineConfig={{ execution_order: ['clipper'], steps: {} }}
            activeProcesses={[]}
            onExecuteAction={vi.fn()}
            onDeleteClip={vi.fn()}
            onDeleteProject={vi.fn()}
          />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText('1 / 1')).toBeDefined();
    // Scoped to the AI output panel: the clip grid renders every highlight as a
    // card now, so the same text also appears below it. Reached through the
    // toggle's aria-controls, which keeps this honest about the panel being
    // wired to its button.
    const panelId = screen
      .getByRole('button', { name: /Hide AI Output/i })
      .getAttribute('aria-controls')!;
    const panel = document.getElementById(panelId) as HTMLElement;
    expect(within(panel).getByText('"only one left"')).toBeDefined();
  });

  it('shows a preview card for every highlight, cut or not', () => {
    renderDetail({
      metadata: metadata([highlight('rendered one', 'clip_000.mp4'), highlight('still a preview')]),
    });

    expect(screen.getByText('Rendered')).toBeDefined();
    expect(screen.getByText('Preview')).toBeDefined();
  });

  // Captions have to be settable before the clipper runs, otherwise the only
  // way to reach them is a clip that has already been rendered without them.
  // The whole form used to sit open in the sticky rail. It is set once and
  // rarely revisited, so the page carries a button and the dialog carries the
  // controls.
  it('keeps the caption form in a dialog rather than in the page', async () => {
    renderDetail();

    expect(await screen.findByRole('button', { name: /Captions/i })).toBeDefined();
    expect(screen.queryByLabelText(/Burn captions into rendered clips/i)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /Captions/i }));

    expect(screen.getByRole('dialog')).toBeDefined();
    expect(screen.getByLabelText(/Burn captions into rendered clips/i)).toBeDefined();
    expect(screen.getByLabelText(/^Preset$/i)).toBeDefined();
  });

  // The aside is `position: sticky` and the clip cards are `position:
  // relative`, so both open a stacking context. A dialog rendered inside one
  // cannot be lifted above the clip grid by any z-index — it has to leave the
  // subtree altogether.
  it('renders the caption dialog outside the sticky aside', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Captions/i }));

    const dialog = screen.getByRole('dialog');
    const aside = document.querySelector('.project-layout__aside');

    expect(aside).not.toBeNull();
    expect(aside!.contains(dialog)).toBe(false);
    expect(dialog.parentElement?.parentElement).toBe(document.body);
  });

  it('saves a caption preset change against the project', async () => {
    const { updateProjectSettings } = await import('../../api');
    renderDetail();

    fireEvent.click(await screen.findByRole('button', { name: /Captions/i }));
    // The options arrive with the preset query, so the select is in the DOM
    // before the value being picked exists on it.
    await screen.findByRole('option', { name: 'Clean Lines' });
    fireEvent.change(screen.getByLabelText(/^Preset$/i), { target: { value: 'clean_lines' } });

    await waitFor(() =>
      expect(vi.mocked(updateProjectSettings)).toHaveBeenCalledWith('p1', {
        captions: { enabled: false, preset: 'clean_lines', overrides: {} },
      })
    );
  });

  // Closed, the button must still admit what it is hiding — otherwise a
  // customised project looks identical to an untouched one.
  it('summarises the caption settings without being opened', async () => {
    renderDetail({
      metadata: {
        ...metadata([highlight('one')]),
        settings: {
          resolution: '1080p',
          aspect_ratio: '16:9',
          captions: { enabled: true, preset: 'karaoke_pop', overrides: { font_size_pct: 9, uppercase: true } },
        },
      },
    });

    // One badge on the trigger rather than a badge plus a summary line: in the
    // options bar this sits beside five other options, and a sentence under
    // each would be five stacked sentences where a row of labels should be.
    const trigger = await screen.findByRole('button', { name: /Captions/i });
    expect(trigger.textContent).toMatch(/On/);
    expect(trigger.textContent).toMatch(/2 adjusted/i);
  });

  it('explains a source video that will not play instead of showing a dead frame', () => {
    renderDetail();

    fireEvent.error(screen.getByLabelText(/Source video/i));

    expect(screen.getByText(/could not be played/i)).toBeDefined();
  });
});
