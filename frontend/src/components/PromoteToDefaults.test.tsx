import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PromoteToDefaults } from './PromoteToDefaults';
import { getSettings, updateSettings } from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return {
    ...actual,
    updateSettings: vi.fn(async () => ({ status: 'success' })),
    getSettings: vi.fn(async () => ({
      settings: {
        description_defaults: { text: 'the old text', template: 'the old template' },
      },
      pipeline_config: { execution_order: [], steps: {} },
    })),
  };
});

const draw = (props: Partial<React.ComponentProps<typeof PromoteToDefaults>> = {}) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PromoteToDefaults build={() => ({ caption_defaults: { enabled: true } })} hint="what this changes" {...props} />
    </QueryClientProvider>
  );

const button = () => screen.getByRole('button', { name: /application default/ });

describe('PromoteToDefaults', () => {
  beforeEach(() => vi.clearAllMocks());

  it('writes what the section built to the application settings', async () => {
    draw();

    await waitFor(() => expect(button()).not.toHaveProperty('disabled', true));
    fireEvent.click(button());

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({ settings: { caption_defaults: { enabled: true } } })
    );
    await screen.findByText(/Saved to the application settings/);
  });

  // The whole key is replaced, so a section that promotes half of one has to
  // build the other half back — which it can only do once the application's own
  // answer has arrived. Clicking before then would blank the other half.
  it('does not write until the application settings have arrived', () => {
    draw({ build: (current) => ({ description_defaults: { ...current.description_defaults, text: 'new' } }) });

    expect(button()).toHaveProperty('disabled', true);
    expect(updateSettings).not.toHaveBeenCalled();
  });

  it('carries the rest of a key it only half fills', async () => {
    draw({ build: (current) => ({ description_defaults: { ...current.description_defaults, text: 'new' } }) });

    await waitFor(() => expect(button()).not.toHaveProperty('disabled', true));
    fireEvent.click(button());

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        settings: { description_defaults: { text: 'new', template: 'the old template' } },
      })
    );
  });

  // A project following the application for everything has nothing of its own,
  // and a live button there would write an empty patch and report success.
  it('is dead, and says why, when the section has nothing of its own', async () => {
    draw({ build: () => ({}), emptyHint: 'this project follows Settings' });

    await screen.findByText('this project follows Settings');
    expect(button()).toHaveProperty('disabled', true);
    expect(screen.queryByText('what this changes')).toBeNull();
  });

  it('does not ask for the application settings when the section fills every key', () => {
    draw({ needsCurrent: false });

    expect(getSettings).not.toHaveBeenCalled();
    expect(button()).not.toHaveProperty('disabled', true);
  });

  it('says the application is unchanged when the write fails', async () => {
    vi.mocked(updateSettings).mockRejectedValueOnce(new Error('nope'));
    draw();

    await waitFor(() => expect(button()).not.toHaveProperty('disabled', true));
    fireEvent.click(button());

    await screen.findByRole('alert');
    expect(screen.getByRole('alert').textContent).toContain('unchanged');
  });
});
