import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PostizPanel } from './PostizPanel';
import { getPostizStatus, updateProjectSettings, type PostizProjectSettings } from '../../api';

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return {
    ...actual,
    updateProjectSettings: vi.fn(async () => ({ status: 'ok' })),
    getPostizStatus: vi.fn(async () => ({
      configured: true,
      api_url: 'https://postiz.example.com/api/public/v1',
      // What Settings says, which is what a project follows until it disagrees.
      selected_channels: ['chan-x'],
      post_type: 'draft' as const,
      channels: [
        { id: 'chan-x', name: 'Coffee and Bytes', identifier: 'x' },
        { id: 'chan-dc', name: 'Samantha', identifier: 'discord' },
      ],
    })),
  };
});

/** A project that has no opinion about anything, which is every new project. */
const FOLLOWING: PostizProjectSettings = {
  channels: null,
  post_type: null,
  channel_settings: {},
  per_day: null,
  text_template: '',
  comment_template: '',
};

const open = async (settings?: Partial<PostizProjectSettings>) => {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PostizPanel projectId="p1" settings={settings && { ...FOLLOWING, ...settings }} />
    </QueryClientProvider>
  );
  fireEvent.click(screen.getByRole('button', { name: /Postiz/ }));
  // Waited on the rendered list rather than on the call: the mock is called
  // before its promise resolves, and asserting there reads a dialog that has
  // not been given the channels yet.
  await waitFor(() => expect(getPostizStatus).toHaveBeenCalled());
  await screen.findByLabelText(/Coffee and Bytes/);
};

describe('PostizPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  // A copy of the application's list stops following it the moment the default
  // changes, and nothing about opening this dialog says the user meant that.
  it('follows the application settings until the project disagrees', async () => {
    await open();

    expect(screen.getByText('Default')).toBeDefined();
    expect(screen.getByLabelText(/Coffee and Bytes/)).toBeChecked();
    expect(screen.getByLabelText(/Samantha/)).not.toBeChecked();
    expect(updateProjectSettings).not.toHaveBeenCalled();
  });

  it('gives the project its own list the first time a channel is ticked', async () => {
    await open();

    fireEvent.click(screen.getByLabelText(/Samantha/));

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', {
        postiz: { channels: ['chan-x', 'chan-dc'] },
      })
    );
  });

  it('lets a project that chose its own channels follow the default again', async () => {
    await open({ channels: ['chan-dc'], post_type: null, channel_settings: {} });

    expect(screen.getByText('1 chosen')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /Follow Settings again/ }));

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { channels: null } })
    );
  });

  // Untick the last one and the project imports nowhere — which is a choice,
  // not the same as having none.
  it('keeps an emptied list as the project’s own', async () => {
    await open({ channels: ['chan-x'], post_type: null, channel_settings: {} });

    fireEvent.click(screen.getByLabelText(/Coffee and Bytes/));

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { channels: [] } })
    );
  });

  it('can schedule for one project while the rest draft', async () => {
    await open();

    fireEvent.change(screen.getByLabelText(/What an import makes/), {
      target: { value: 'schedule' },
    });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { post_type: 'schedule' } })
    );
  });

  it('sends the project back to the application default for post type', async () => {
    await open({ channels: null, post_type: 'now', channel_settings: {} });

    fireEvent.change(screen.getByLabelText(/What an import makes/), { target: { value: '' } });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { post_type: null } })
    );
  });

  // "Follow Settings" and "all on the same day" are different answers, and a
  // control that stored 0 for both would silently freeze a project on the
  // default it happened to have when it was opened.
  it('tells following the application apart from choosing all at once', async () => {
    await open();

    expect((screen.getByLabelText(/How many land per day/) as HTMLSelectElement).value).toBe('');

    fireEvent.change(screen.getByLabelText(/How many land per day/), { target: { value: '0' } });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { per_day: 0 } })
    );
  });

  it('drips one project a day while the rest go out together', async () => {
    await open();

    fireEvent.change(screen.getByLabelText(/How many land per day/), { target: { value: '2' } });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { per_day: 2 } })
    );
  });

  it('sends a cadence back to the application default', async () => {
    await open({ per_day: 3 });

    fireEvent.change(screen.getByLabelText(/How many land per day/), { target: { value: '' } });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { per_day: null } })
    );
  });

  // Templates are paragraphs typed once, so they are written when the user
  // leaves the box rather than on every keystroke.
  it('saves the post template when the box is left', async () => {
    await open();

    const box = screen.getByLabelText(/What each post says/);
    fireEvent.change(box, { target: { value: '{platform.post}' } });
    expect(updateProjectSettings).not.toHaveBeenCalled();

    fireEvent.blur(box);

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', {
        postiz: { text_template: '{platform.post}' },
      })
    );
  });

  it('saves the comment template when the box is left', async () => {
    await open();

    const box = screen.getByLabelText(/Comment under the post/);
    fireEvent.change(box, { target: { value: 'Full episode: {project.source_url}' } });
    fireEvent.blur(box);

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', {
        postiz: { comment_template: 'Full episode: {project.source_url}' },
      })
    );
  });

  it('does not save a template that was opened and left untouched', async () => {
    await open({ text_template: '{platform.post}' });

    fireEvent.blur(screen.getByLabelText(/What each post says/));

    expect(updateProjectSettings).not.toHaveBeenCalled();
  });
});
