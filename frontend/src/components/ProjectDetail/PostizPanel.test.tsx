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
  start_date: null,
  day_start_hour: null,
  day_end_hour: null,
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

    // The badge, not the "Default" option each hour select offers.
    expect(screen.getByText('Default', { selector: '.status-badge' })).toBeDefined();
    expect(screen.getByLabelText(/Coffee and Bytes/)).toBeChecked();
    expect(screen.getByLabelText(/Samantha/)).not.toBeChecked();
    expect(updateProjectSettings).not.toHaveBeenCalled();
  });

  // The badge read the channel list alone, so a project that had been given its
  // own schedule or its own wording still announced itself as following the
  // application — the one place the user looks to see that a change took.
  it('stops saying Default once any setting is the project’s own', async () => {
    await open({ post_type: 'schedule', per_day: 2 });

    expect(screen.getByText('2 chosen', { selector: '.status-badge' })).toBeDefined();
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

    expect(screen.getByText('1 channel')).toBeDefined();
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

  // The rest of the calendar, asked exactly as the YouTube panel asks it. A
  // project that can say "two a day" but not "starting Monday, between seven
  // and eleven" sends one set of clips out on two calendars.
  it('gives the project its own first day', async () => {
    await open();

    fireEvent.change(screen.getByLabelText(/First post lands on/), {
      target: { value: '2026-09-01' },
    });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', {
        postiz: { start_date: '2026-09-01' },
      })
    );
  });

  it('sends the first day back to the application default when it is cleared', async () => {
    await open({ start_date: '2026-09-01' });
    const date = screen.getByLabelText(/First post lands on/);

    // Cleared, then left: a date input reads empty half-typed too, so the
    // empty is only an answer once the user is out of the field.
    fireEvent.change(date, { target: { value: '' } });
    fireEvent.blur(date);

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { start_date: null } })
    );
  });

  it('gives the project its own hours of the day', async () => {
    await open();

    expect((screen.getByLabelText(/From/) as HTMLSelectElement).value).toBe('');
    fireEvent.change(screen.getByLabelText(/From/), { target: { value: '7' } });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { day_start_hour: 7 } })
    );
  });

  // Midnight is an hour, not an absent answer: a control that stored null for
  // it would put a project back on the default it was trying to leave.
  it('tells midnight apart from following the application', async () => {
    await open();

    fireEvent.change(screen.getByLabelText(/^to$/), { target: { value: '0' } });

    await waitFor(() =>
      expect(updateProjectSettings).toHaveBeenCalledWith('p1', { postiz: { day_end_hour: 0 } })
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
