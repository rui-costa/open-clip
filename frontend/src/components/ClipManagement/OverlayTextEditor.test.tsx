import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useState } from 'react';
import { OverlayTextEditor } from './OverlayTextEditor';
import { stubFrameSize } from '../../test/stubFrame';
import { DEFAULT_OVERLAY_TEXT, updateClipOverlay, type OverlayText } from '../../api';

vi.mock('../../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api')>()),
  updateClipOverlay: vi.fn().mockResolvedValue({ status: 'success', overlay: null }),
}));

beforeEach(() => {
  vi.mocked(updateClipOverlay).mockClear();
  stubFrameSize(400);
});

/**
 * The dialog with the page's half of the contract around it: the draft lives
 * above it, which is what lets the picture behind redraw per keystroke.
 */
const Harness: React.FC<{ onClose?: () => void }> = ({ onClose = () => {} }) => {
  const [draft, setDraft] = useState<OverlayText | null>(null);
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <OverlayTextEditor
        projectId="test-project"
        clipIndex={0}
        isOpen
        onClose={onClose}
        value={draft ?? DEFAULT_OVERLAY_TEXT}
        onChange={setDraft}
      />
    </QueryClientProvider>
  );
};

const type = (text: string) =>
  fireEvent.change(screen.getByLabelText('Text'), { target: { value: text } });

describe('OverlayTextEditor', () => {
  // Saving is debounced, and a debounce is a timer nobody is obliged to wait
  // for: a card unmounted on its way out — scrolled away, or the grid rebuilt
  // by a poll — takes the pending save with it. Leaving on purpose therefore
  // sends immediately rather than arming another timer.
  it('sends a title typed and closed straight away, without waiting out the debounce', async () => {
    vi.useFakeTimers();
    try {
      render(<Harness />);
      type('Cold open');
      fireEvent.click(screen.getByRole('button', { name: 'Save and close' }));

      // Zero, which lets the mutation's own microtasks run but leaves the 300ms
      // debounce timer unfired: what arrives here is the flush.
      await vi.advanceTimersByTimeAsync(0);
      expect(updateClipOverlay).toHaveBeenCalledTimes(1);
      expect(vi.mocked(updateClipOverlay).mock.calls[0][2]).toMatchObject({ text: 'Cold open' });
    } finally {
      vi.useRealTimers();
    }
  });

  it('closes the dialog once it has sent it', async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    type('Cold open');
    fireEvent.click(screen.getByRole('button', { name: 'Save and close' }));

    expect(onClose).toHaveBeenCalled();
    await waitFor(() => expect(updateClipOverlay).toHaveBeenCalledTimes(1));
  });

  // Every way out is the same handler, so dismissing the dialog is not a way to
  // lose the last thing typed into it.
  it('sends it when the dialog is dismissed rather than saved', async () => {
    render(<Harness />);
    type('Cold open');
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    await waitFor(() => expect(updateClipOverlay).toHaveBeenCalledTimes(1));
  });

  it('removes the title rather than saving the edit on its way out', async () => {
    render(<Harness />);
    type('Cold open');
    fireEvent.click(screen.getByRole('button', { name: 'Remove this title' }));

    await waitFor(() => expect(updateClipOverlay).toHaveBeenCalledTimes(1));
    expect(vi.mocked(updateClipOverlay).mock.calls[0][2]).toBeNull();
  });

  it('debounces typing into one request rather than one per keystroke', async () => {
    render(<Harness />);
    type('C');
    type('Co');
    type('Cold open');
    fireEvent.click(screen.getByRole('button', { name: 'Save and close' }));

    await waitFor(() => expect(updateClipOverlay).toHaveBeenCalledTimes(1));
  });

  it('places the title against a picture when one is given to it', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <OverlayTextEditor
          projectId="test-project"
          clipIndex={0}
          isOpen
          onClose={() => {}}
          value={{ ...DEFAULT_OVERLAY_TEXT, text: 'Cold open' }}
          onChange={() => {}}
          preview={{
            src: 'http://localhost:8000/clip.mp4',
            start: 0,
            end: null,
            isPreview: false,
            aspectRatio: 9 / 16,
            label: 'Clip 1',
          }}
        />
      </QueryClientProvider>
    );

    expect(document.querySelector('video')?.getAttribute('src')).toBe('http://localhost:8000/clip.mp4');
    // Drawn on the picture, and in the textarea: two of them, not one.
    expect(screen.getAllByText('Cold open').length).toBeGreaterThan(0);
  });
});
