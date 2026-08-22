import React, { useEffect, useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../Modal';
import { DescriptionFieldHelp } from '../DescriptionFieldHelp';
import {
  getPostizStatus,
  updateProjectSettings,
  type PostizProjectSettings,
} from '../../api';

interface PostizPanelProps {
  projectId: string;
  /** What the project has stored, or undefined for one created before this existed. */
  settings: PostizProjectSettings | undefined;
  /** See CaptionStyler: `panel` is a row with a summary, `inline` is one text action. */
  variant?: 'panel' | 'inline';
}

const EMPTY: PostizProjectSettings = {
  channels: null,
  post_type: null,
  channel_settings: {},
  per_day: null,
  text_template: '',
  comment_template: '',
};

/** Fields that mean something in a Postiz post and nothing in a YouTube description. */
const POSTIZ_FIELDS = [
  {
    field: 'platform.post',
    description: 'What the model wrote for the platform this post is going to',
  },
  { field: 'platform.name', description: 'The platform itself, e.g. x, linkedin' },
];

/**
 * Where this project's clips go, when that is not where everything else goes.
 *
 * One machine has one Postiz account, and the projects on it are not one thing:
 * a company's podcast and somebody's side project are cut on the same install
 * and must not land in the same accounts. Settings holds the default; this is
 * where a project disagrees with it.
 *
 * Following the application is a state of its own rather than a copy of its
 * list — the difference matters, because a copy stops following the moment the
 * default changes, and nothing about ticking boxes here says the user meant to
 * freeze them.
 */
export const PostizPanel: React.FC<PostizPanelProps> = ({ projectId, settings, variant = 'panel' }) => {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const postTypeId = useId();
  const perDayId = useId();
  const textId = useId();
  const commentId = useId();

  // Asked only while the dialog is open: it is a round trip to Postiz, and the
  // channel list is not something the project page needs otherwise.
  const { data: postiz } = useQuery({
    queryKey: ['postizStatus'],
    queryFn: getPostizStatus,
    enabled: isOpen,
    retry: false,
  });

  const mutation = useMutation({
    mutationFn: (next: Partial<PostizProjectSettings>) =>
      updateProjectSettings(projectId, { postiz: next }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projectMetadata', projectId] });
    },
  });

  const stored = settings ?? EMPTY;
  const follows = stored.channels === null;

  // The two templates are paragraphs typed once, so they are held locally and
  // written when the user leaves the box — and re-synced only while the dialog
  // is closed, so a background metadata refresh cannot overwrite half a
  // sentence someone is still typing.
  const [text, setText] = useState(stored.text_template ?? '');
  const [comment, setComment] = useState(stored.comment_template ?? '');
  useEffect(() => {
    if (!isOpen) {
      setText(settings?.text_template ?? '');
      setComment(settings?.comment_template ?? '');
    }
  }, [settings, isOpen]);

  // What the boxes show: this project's choice, or — while it follows — the
  // application's, so the ticks read as what would actually happen.
  const ticked = follows ? postiz?.selected_channels ?? [] : stored.channels ?? [];

  const toggle = (id: string) => {
    const next = ticked.includes(id) ? ticked.filter((entry) => entry !== id) : [...ticked, id];
    // The first tick is also the moment this project stops following the
    // application, which is why an empty list is sent rather than null.
    mutation.mutate({ channels: next });
  };

  const badge = (
    <span
      className="status-badge"
      style={
        follows
          ? undefined
          : { background: 'var(--accent)', color: 'var(--on-accent, var(--bg))' }
      }
    >
      {follows ? 'Default' : `${stored.channels?.length ?? 0} chosen`}
    </span>
  );

  const labelStyle: React.CSSProperties = {
    fontWeight: 900,
    fontSize: '0.65rem',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  };

  const fieldStyle: React.CSSProperties = {
    padding: 'var(--space-sm)',
    background: 'var(--bg)',
    color: 'var(--text)',
    border: 'var(--border)',
    fontFamily: 'inherit',
    fontSize: '0.85rem',
    width: '100%',
    minHeight: '44px',
  };

  return (
    <>
      {variant === 'inline' ? (
        <button type="button" className="text-action" onClick={() => setIsOpen(true)}>
          Postiz
          {badge}
        </button>
      ) : (
        <button type="button" className="panel-button" onClick={() => setIsOpen(true)}>
          <span>Postiz</span>
          {badge}
        </button>
      )}

      <Modal isOpen={isOpen} title="Postiz for this project" onClose={() => setIsOpen(false)} maxWidth="620px">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          {!postiz?.configured && (
            <p style={{ margin: 0, fontSize: '0.8rem' }}>
              Postiz is not set up yet. Add an API key in Settings and the channels appear here.
            </p>
          )}
          {postiz?.error && (
            <p role="alert" style={{ margin: 0, fontSize: '0.8rem', color: 'var(--error)', overflowWrap: 'anywhere' }}>
              {postiz.error}
            </p>
          )}

          {(postiz?.channels?.length ?? 0) > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              <span style={labelStyle}>Channels</span>
              <p style={{ margin: 0, fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                {follows
                  ? 'Following Settings: change the default there and this project follows it. Tick anything here and this project stops following and keeps its own list.'
                  : 'This project has its own list. Nothing ticked means it imports nowhere.'}
              </p>
              {(postiz?.channels ?? []).map((channel) => (
                <label
                  key={channel.id}
                  style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', fontSize: '0.85rem', minHeight: '44px' }}
                >
                  <input type="checkbox" checked={ticked.includes(channel.id)} onChange={() => toggle(channel.id)} />
                  <span>
                    {channel.name || channel.id}
                    {channel.identifier ? ` (${channel.identifier})` : ''}
                    {channel.disabled ? ' — disabled in Postiz' : ''}
                  </span>
                </label>
              ))}
              {!follows && (
                // The way back. Without it, a project that has ever been
                // ticked can never follow the default again.
                <button
                  type="button"
                  className="text-action"
                  onClick={() => mutation.mutate({ channels: null })}
                >
                  Follow Settings again
                </button>
              )}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <label htmlFor={postTypeId} style={labelStyle}>What an import makes</label>
            <select
              id={postTypeId}
              value={stored.post_type ?? ''}
              onChange={(e) =>
                mutation.mutate({
                  post_type: (e.target.value || null) as PostizProjectSettings['post_type'],
                })
              }
              style={fieldStyle}
            >
              <option value="">
                Whatever Settings says{postiz?.post_type ? ` (${postiz.post_type})` : ''}
              </option>
              <option value="draft">A draft, for you to send</option>
              <option value="schedule">A scheduled post</option>
              <option value="now">Posted immediately</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <label htmlFor={perDayId} style={labelStyle}>How many land per day</label>
            <select
              id={perDayId}
              // An empty string is "follow Settings" and 0 is "all on the same
              // day" — two different answers, which is why the value is not
              // simply the number.
              value={stored.per_day === null ? '' : String(stored.per_day)}
              onChange={(e) =>
                mutation.mutate({ per_day: e.target.value === '' ? null : Number(e.target.value) })
              }
              style={fieldStyle}
            >
              <option value="">Whatever Settings says</option>
              <option value="0">All on the same day</option>
              <option value="1">1 per day</option>
              <option value="2">2 per day</option>
              <option value="3">3 per day</option>
              <option value="4">4 per day</option>
              <option value="6">6 per day</option>
            </select>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
              A clip keeps its slot however it was imported, so re-importing one moves nothing.
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <label htmlFor={textId} style={labelStyle}>What each post says</label>
            <textarea
              id={textId}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onBlur={() => {
                if (text !== (stored.text_template ?? '')) mutation.mutate({ text_template: text });
              }}
              placeholder="Empty: use the template from Settings"
              style={{ ...fieldStyle, minHeight: '110px', fontFamily: 'monospace', lineHeight: 1.4 }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <label htmlFor={commentId} style={labelStyle}>Comment under the post</label>
            <textarea
              id={commentId}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              onBlur={() => {
                if (comment !== (stored.comment_template ?? '')) {
                  mutation.mutate({ comment_template: comment });
                }
              }}
              placeholder="Empty: use the one from Settings"
              style={{ ...fieldStyle, minHeight: '70px', fontFamily: 'monospace', lineHeight: 1.4 }}
            />
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
              Posted as a thread or first comment where the platform has one. Left out when it
              renders empty, so a project with no source URL gets no dangling "Full episode:".
            </span>
            <DescriptionFieldHelp extra={POSTIZ_FIELDS} />
          </div>
        </div>

        {mutation.isError && (
          <p role="alert" style={{ margin: 'var(--space-md) 0 0 0', fontSize: '0.75rem', color: 'var(--error)' }}>
            Could not save that. Imports would use the last saved setting, not this one.
          </p>
        )}
      </Modal>
    </>
  );
};
