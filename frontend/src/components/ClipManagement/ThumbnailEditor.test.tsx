import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ThumbnailEditor } from './ThumbnailEditor';
import { stubFrameSize } from '../../test/stubFrame';
import {
  DEFAULT_THUMBNAIL,
  generateClipThumbnail,
  getClipThumbnail,
  updateClipThumbnail,
  type ThumbnailSettings,
} from '../../api';

vi.mock('../../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api')>()),
  getClipThumbnail: vi.fn(),
  updateClipThumbnail: vi.fn().mockResolvedValue({ status: 'success', thumbnail: null }),
  generateClipThumbnail: vi.fn(),
}));

const stored = (overrides: Partial<ThumbnailSettings> = {}): ThumbnailSettings => ({
  ...DEFAULT_THUMBNAIL,
  ...overrides,
});

beforeEach(() => {
  vi.mocked(updateClipThumbnail).mockClear();
  vi.mocked(generateClipThumbnail).mockClear();
  vi.mocked(getClipThumbnail).mockResolvedValue({
    settings: stored(),
    title: null,
    title_font: null,
    duration: 4,
    exists: false,
  });
  stubFrameSize(400);
});

const preview = {
  src: 'http://localhost:8000/clip.mp4',
  start: 0,
  end: null,
  isPreview: false,
  aspectRatio: 9 / 16,
  label: 'Clip 1',
};

const renderEditor = (props: Partial<React.ComponentProps<typeof ThumbnailEditor>> = {}) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ThumbnailEditor
        projectId="test-project"
        clipIndex={0}
        isOpen
        onClose={() => {}}
        preview={preview}
        {...props}
      />
    </QueryClientProvider>
  );

/** The settings sent by the most recent save. */
const lastSaved = () => vi.mocked(updateClipThumbnail).mock.calls.at(-1)?.[2];

describe('ThumbnailEditor', () => {
  it('opens on the defaults: the clip’s title on, the subtitles off', async () => {
    renderEditor();

    await waitFor(() => expect(getClipThumbnail).toHaveBeenCalled());
    expect((screen.getByLabelText(/Draw the clip’s title/) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText(/Show the subtitles/) as HTMLInputElement).checked).toBe(false);
  });

  it('opens the picker on the frame already chosen rather than rewinding it', async () => {
    vi.mocked(getClipThumbnail).mockResolvedValue({
      settings: stored({ frame_time: 2.5 }),
      title: null,
      title_font: null,
      duration: 4,
      exists: false,
    });
    renderEditor();

    await waitFor(() => expect(screen.getByText(/2\.50s into the clip/)).toBeDefined());
  });

  it('takes the frame the player is showing', async () => {
    // The window has an end here, unlike the cut-file preview above: jsdom
    // reports no duration for a <video>, so a clip that relies on the file's
    // own length has nothing to scrub through.
    renderEditor({ preview: { ...preview, end: 4, isPreview: true } });
    await waitFor(() => expect(getClipThumbnail).toHaveBeenCalled());

    // Scrubbing is what picking a frame is; the transport reports the position
    // and the button turns it into the choice.
    fireEvent.change(screen.getByLabelText('Position within Clip 1'), { target: { value: '1.5' } });
    fireEvent.click(screen.getByRole('button', { name: /Use the frame showing now/ }));

    await waitFor(() => expect(updateClipThumbnail).toHaveBeenCalled());
    expect(lastSaved()).toMatchObject({ frame_time: 1.5 });
  });

  it('saves the subtitles being switched on for the still', async () => {
    renderEditor();
    await waitFor(() => expect(getClipThumbnail).toHaveBeenCalled());

    fireEvent.click(screen.getByLabelText(/Show the subtitles/));

    await waitFor(() => expect(updateClipThumbnail).toHaveBeenCalled());
    expect(lastSaved()).toMatchObject({ show_captions: true });
  });

  it('adds extra text that never reaches the video', async () => {
    renderEditor();
    await waitFor(() => expect(getClipThumbnail).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText('Extra text'), { target: { value: 'Part two' } });

    await waitFor(() => expect(updateClipThumbnail).toHaveBeenCalled());
    expect(lastSaved()?.extra).toMatchObject({ text: 'Part two' });
  });

  it('hands the clip back to the defaults rather than saving the edit on its way out', async () => {
    renderEditor();
    await waitFor(() => expect(getClipThumbnail).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText('Extra text'), { target: { value: 'Part two' } });
    fireEvent.click(screen.getByRole('button', { name: 'Back to defaults' }));

    await waitFor(() => expect(updateClipThumbnail).toHaveBeenCalled());
    expect(lastSaved()).toBeNull();
  });

  it('shows the picture once it has been made', async () => {
    vi.mocked(generateClipThumbnail).mockResolvedValue({
      status: 'success',
      thumbnail: stored({ generated_filename: 'clip_000.jpg', generated_at: '2026-01-01T00:00:00' }),
    });
    renderEditor();
    await waitFor(() => expect(getClipThumbnail).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Make the thumbnail' }));

    const image = await screen.findByAltText('Thumbnail for clip 1');
    expect(image.getAttribute('src')).toContain('/thumbnails/clip_000.jpg');
    // Versioned by when it was made: the filename never changes, so without it
    // a remade thumbnail shows the copy the browser already has.
    expect(image.getAttribute('src')).toContain('v=2026-01-01');
  });

  it('reports a failed render rather than leaving the button looking untouched', async () => {
    vi.mocked(generateClipThumbnail).mockRejectedValue(new Error('The source video is missing.'));
    renderEditor();
    await waitFor(() => expect(getClipThumbnail).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Make the thumbnail' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The source video is missing.');
  });
});
