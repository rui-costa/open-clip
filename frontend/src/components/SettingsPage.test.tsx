import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SettingsPage } from './SettingsPage';
import * as api from '../api';

/**
 * Cover for the YouTube channel panel alone: whether a connection is short of
 * a permission, and what the button does about it.
 */

const settings = {
  settings: {
    gemini_api_key: '',
    youtube_client_secrets: { installed: { client_id: 'a', client_secret: 'b' } },
    theme: 'light' as const,
    video_defaults: { resolution: 'keep original', aspect_ratio: 'keep original' },
  },
  pipeline_config: { execution_order: [], steps: {} },
};

const renderPage = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SettingsPage theme="light" setTheme={() => {}} />
    </QueryClientProvider>
  );
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, 'getSettings').mockResolvedValue(settings as never);
  vi.spyOn(api, 'getResolutionMap').mockResolvedValue({});
  vi.spyOn(api, 'getAspectRatioMap').mockResolvedValue({});
  vi.spyOn(api, 'getCaptionStyles').mockResolvedValue({} as never);
  vi.spyOn(api, 'getDescriptionFields').mockResolvedValue({} as never);
});

describe('SettingsPage YouTube channel', () => {
  it('says a token short of the read scope is connected, and why that matters', async () => {
    vi.spyOn(api, 'getYoutubeStatus').mockResolvedValue({
      connected: true,
      account: 'someone@example.com',
      missing_scopes: ['https://www.googleapis.com/auth/youtube.readonly'],
      has_client_secrets: true,
    });

    renderPage();

    expect(await screen.findByText(/Connected as someone@example.com/)).toBeInTheDocument();
    expect(screen.getByText(/Missing permission/)).toBeInTheDocument();
    // Uploads are unaffected, so the button is an offer rather than a demand.
    expect(screen.getByRole('button', { name: /Reconnect Channel/i })).toBeEnabled();
  });

  it('opens the consent Google returns in a tab of its own', async () => {
    vi.spyOn(api, 'getYoutubeStatus').mockResolvedValue({
      connected: false,
      reason: 'No YouTube account has been connected yet.',
      has_client_secrets: true,
    });
    const connect = vi
      .spyOn(api, 'connectYoutube')
      .mockResolvedValue({ authorization_url: 'https://accounts.google.com/o/oauth2/auth?x=1' });
    const open = vi.spyOn(window, 'open').mockReturnValue(null);

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /Connect Channel/i }));

    await waitFor(() => expect(connect).toHaveBeenCalled());
    await waitFor(() =>
      expect(open).toHaveBeenCalledWith(
        'https://accounts.google.com/o/oauth2/auth?x=1',
        '_blank',
        'noopener'
      )
    );
  });

  it('opens another sign-in while one is still waiting', async () => {
    // Closing the tab leaves the backend waiting for a redirect that is never
    // coming. That is the moment this button matters most, so it stays live
    // and simply opens another window.
    vi.spyOn(api, 'getYoutubeStatus').mockResolvedValue({
      connected: false,
      has_client_secrets: true,
      consent: { pending: true, completed: false, cancelled: false, error: null },
    });
    const connect = vi
      .spyOn(api, 'connectYoutube')
      .mockResolvedValue({ authorization_url: 'https://accounts.google.com/o/oauth2/auth?x=2' });
    vi.spyOn(window, 'open').mockReturnValue(null);

    renderPage();
    const again = await screen.findByRole('button', { name: /Open Sign-in Again/i });
    expect(again).toBeEnabled();
    fireEvent.click(again);

    await waitFor(() => expect(connect).toHaveBeenCalled());
  });

  it('can abandon a consent left waiting', async () => {
    vi.spyOn(api, 'getYoutubeStatus').mockResolvedValue({
      connected: false,
      has_client_secrets: true,
      consent: { pending: true, completed: false, cancelled: false, error: null },
    });
    const cancel = vi.spyOn(api, 'cancelYoutubeConnect').mockResolvedValue({ status: 'success' });

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /^Cancel$/i }));

    await waitFor(() => expect(cancel).toHaveBeenCalled());
  });

  it('cannot start a consent before the client secrets are in', async () => {
    vi.spyOn(api, 'getSettings').mockResolvedValue({
      ...settings,
      settings: { ...settings.settings, youtube_client_secrets: null },
    } as never);
    vi.spyOn(api, 'getYoutubeStatus').mockResolvedValue({
      connected: false,
      reason: 'No YouTube account has been connected yet.',
      has_client_secrets: false,
    });

    renderPage();

    expect(await screen.findByRole('button', { name: /Connect Channel/i })).toBeDisabled();
    expect(screen.getByText(/Add the client secrets above first/)).toBeInTheDocument();
  });
});
