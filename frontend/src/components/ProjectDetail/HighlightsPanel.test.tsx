import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HighlightsPanel } from './HighlightsPanel';
import { getSettings, updateProjectSettings, type HighlightProjectSettings } from '../../api';

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return {
    ...actual,
    updateProjectSettings: vi.fn(async () => ({ status: 'ok' })),
    getSettings: vi.fn(async () => ({
      // What Settings says, which is what a project follows until it disagrees.
      settings: { highlight_defaults: { min_clips: 4, max_clips: 6, max_duration: 45 } },
      pipeline_config: { execution_order: [], steps: {} },
    })),
  };
});

/** A project that has no opinion about anything, which is every new project. */
const FOLLOWING: HighlightProjectSettings = {
  min_clips: null,
  max_clips: null,
  min_duration: null,
  max_duration: null,
  guidance: '',
};

const open = async (settings?: Partial<HighlightProjectSettings>) => {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <HighlightsPanel projectId="p1" settings={settings && { ...FOLLOWING, ...settings }} />
    </QueryClientProvider>
  );
  fireEvent.click(screen.getByRole('button', { name: /Highlights/ }));
  await waitFor(() => expect(getSettings).toHaveBeenCalled());
  await screen.findByLabelText(/Fewest clips/);
};

describe('HighlightsPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('follows the application settings until the project disagrees', async () => {
    await open();

    // Empty fields showing the application's numbers as placeholders: a copy
    // of them would stop following the moment the default changed, and opening
    // this dialog says nothing about wanting that.
    expect(screen.getByLabelText(/Fewest clips/)).toHaveValue(null);
    expect(screen.getByLabelText(/Fewest clips/)).toHaveAttribute('placeholder', '4');
    expect(screen.getByLabelText(/Longest clip/)).toHaveAttribute('placeholder', '45');
    // Untouched by the application, so the number the prompt ships with.
    expect(screen.getByLabelText(/Shortest clip/)).toHaveAttribute('placeholder', '18');
    expect(updateProjectSettings).not.toHaveBeenCalled();
  });

  it('saves a number when the field is left', async () => {
    await open();

    const field = screen.getByLabelText(/Most clips/);
    fireEvent.change(field, { target: { value: '3' } });
    fireEvent.blur(field);

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { highlights: { max_clips: 3 } })
    );
  });

  it('puts a cleared field back under the application settings', async () => {
    await open({ max_clips: 3 });

    const field = screen.getByLabelText(/Most clips/);
    fireEvent.change(field, { target: { value: '' } });
    fireEvent.blur(field);

    // Null, not zero: a run told to return at most zero clips is not what
    // emptying a field means.
    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { highlights: { max_clips: null } })
    );
  });

  it('does not send a number the backend would only throw away', async () => {
    await open();

    const field = screen.getByLabelText(/Most clips/);
    fireEvent.change(field, { target: { value: '5000' } });
    fireEvent.blur(field);

    await waitFor(() => expect(getSettings).toHaveBeenCalled());
    expect(updateProjectSettings).not.toHaveBeenCalled();
  });

  it('saves the project guidance when the field is left', async () => {
    await open();

    const field = screen.getByLabelText(/What counts as a highlight/);
    fireEvent.change(field, { target: { value: 'only the guest' } });
    fireEvent.blur(field);

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', {
        highlights: { guidance: 'only the guest' },
      })
    );
  });

  it('says on the badge what this project asks for once it has chosen', async () => {
    await open({ min_clips: 2, max_clips: 3 });

    expect(screen.getByText('2–3 clips', { selector: '.status-badge' })).toBeDefined();
  });
});
