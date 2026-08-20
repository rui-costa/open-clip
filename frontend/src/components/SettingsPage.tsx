import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, getResolutionMap, getAspectRatioMap, getCaptionStyles, getDescriptionFields, getYoutubeStatus, connectYoutube, cancelYoutubeConnect, type SettingsResponse } from '../api';
import { useDebounce } from '../hooks/useDebounce';
import { DescriptionFieldHelp } from './DescriptionFieldHelp';

interface SettingsPageProps {
  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ theme, setTheme }) => {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<SettingsResponse>({
    queryKey: ['settings'],
    queryFn: getSettings as () => Promise<SettingsResponse>,
  });

  // These share their cache entry with the project page, which needs the
  // values ("1920x1080") and not just the names, so the map is what the key
  // holds everywhere.
  const { data: resolutionsData } = useQuery({
    queryKey: ['resolutions'],
    queryFn: getResolutionMap,
  });

  const { data: aspectRatiosData } = useQuery({
    queryKey: ['aspectRatios'],
    queryFn: getAspectRatioMap,
  });

  const { data: captionStyles } = useQuery({
    queryKey: ['captionStyles'],
    queryFn: getCaptionStyles,
  });

  // Only for the placeholder text on the template box: an empty template means
  // the app's own, and the box should show which one that is.
  const { data: descriptionFields } = useQuery({
    queryKey: ['descriptionFields'],
    queryFn: getDescriptionFields,
  });

  // Polled only while a consent is open in the other tab: the answer changes
  // when the user finishes there, which this page has no other way to hear
  // about.
  const { data: youtube } = useQuery({
    queryKey: ['youtubeStatus'],
    queryFn: getYoutubeStatus,
    refetchInterval: (query) => (query.state.data?.consent?.pending ? 2000 : false),
  });

  const connectMutation = useMutation({
    mutationFn: connectYoutube,
    onSuccess: ({ authorization_url }) => {
      // A new tab rather than a redirect: leaving this page would lose the
      // settings the user is in the middle of editing.
      window.open(authorization_url, '_blank', 'noopener');
      queryClient.invalidateQueries({ queryKey: ['youtubeStatus'] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: cancelYoutubeConnect,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['youtubeStatus'] }),
  });

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      queryClient.invalidateQueries({ queryKey: ['pipelineConfig'] });
    },
  });
  // `mutate` is referentially stable across renders; the mutation object is
  // not, so depend on this rather than on `updateMutation`.
  const { mutate: saveSettings } = updateMutation;

  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  // Saved when the user leaves the box rather than on every keystroke: these
  // are paragraphs, and each save is a write to disk.
  const [descriptionText, setDescriptionText] = useState('');
  const [descriptionTemplate, setDescriptionTemplate] = useState('');
  const [ytSecrets, setYtSecrets] = useState('');
  const [jsonError, setJsonError] = useState(false);

  const debouncedApiKey = useDebounce(apiKey, 500);
  const debouncedYtSecrets = useDebounce(ytSecrets, 500);

  // Track whether the local state has been initialized from server data
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (data) {
      setApiKey(data.settings?.gemini_api_key || '');
      setYtSecrets(data.settings?.youtube_client_secrets ? JSON.stringify(data.settings.youtube_client_secrets, null, 2) : '');
      setDescriptionText(data.settings?.description_defaults?.text || '');
      setDescriptionTemplate(data.settings?.description_defaults?.template || '');
      setInitialized(true);
    }
  }, [data]);

  useEffect(() => {
    if (!initialized || !data) return;
    const serverValue = data.settings?.gemini_api_key || '';
    if (debouncedApiKey !== serverValue) {
      saveSettings({ settings: { gemini_api_key: debouncedApiKey } });
    }
  }, [debouncedApiKey, data, initialized, saveSettings]);

  useEffect(() => {
    if (!initialized || !data) return;
    const serverValue = data.settings?.youtube_client_secrets ? JSON.stringify(data.settings.youtube_client_secrets, null, 2) : '';
    if (debouncedYtSecrets !== serverValue) {
      try {
        const parsed = JSON.parse(debouncedYtSecrets);
        saveSettings({ settings: { youtube_client_secrets: parsed } });
        setJsonError(false);
      } catch {
        setJsonError(true);
      }
    }
  }, [debouncedYtSecrets, data, initialized, saveSettings]);

  if (isLoading) return <div style={{ padding: 'var(--space-md)', fontWeight: 'bold', textTransform: 'uppercase' }}>Loading settings...</div>;

  const settings = data?.settings || { gemini_api_key: '', youtube_client_secrets: null, theme: 'light' as const, video_defaults: { resolution: 'keep original', aspect_ratio: 'keep original' } };
  const pipelineConfig = data?.pipeline_config || { execution_order: [], steps: {} };

  const getSaveStatus = () => {
    if (updateMutation.isError) return { text: 'ERROR SAVING!', color: 'var(--error)' };
    if (updateMutation.isPending) return { text: 'SAVING...', color: 'var(--text)' };
    if (updateMutation.isSuccess) return { text: 'SAVED!', color: 'green' };
    return { text: 'All changes saved', color: 'var(--text)', opacity: 0.6 };
  };

  const status = getSaveStatus();

  const inputStyle: React.CSSProperties = {
    padding: 'var(--space-md)',
    background: 'var(--bg)',
    color: 'var(--text)',
    border: 'var(--border)',
    fontFamily: 'inherit',
    width: '100%',
  };

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      gap: 'var(--space-lg)',
      width: '100%',
      maxWidth: '800px',
      margin: '0 auto',
      padding: 'var(--space-md)'
    }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'flex-end',
        borderBottom: 'var(--border)',
        paddingBottom: 'var(--space-sm)'
      }}>
        <h1 style={{ 
          fontSize: '2.5rem', 
          fontWeight: 900, 
          textTransform: 'uppercase',
          margin: 0,
        }}>Settings</h1>
        <span style={{ 
          fontSize: '0.8rem', 
          fontWeight: 'bold', 
          textTransform: 'uppercase',
          color: status.color,
          opacity: status.opacity || 1,
        }}>
          {status.text}
        </span>
      </div>

      {updateMutation.isError && (
        <div style={{ 
          border: '1px solid var(--error)', 
          padding: 'var(--space-sm)', 
          color: 'var(--error)',
          fontWeight: 'bold',
          textTransform: 'uppercase',
        }}>
          Failed to save settings. Please check your connection.
        </div>
      )}

      {/* Appearance Section */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase', fontWeight: 900 }}>Appearance</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
          <span style={{ fontWeight: 'bold', textTransform: 'uppercase' }}>Theme:</span>
          <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
            {(['light', 'dark'] as const).map((t) => (
              <button 
                key={t}
                onClick={() => {
                  setTheme(t);
                  updateMutation.mutate({ settings: { theme: t } });
                }}
                style={{
                  padding: 'var(--space-md) var(--space-lg)',
                  background: theme === t ? 'var(--text)' : 'var(--bg)',
                  color: theme === t ? 'var(--bg)' : 'var(--text)',
                  border: 'var(--border)',
                  fontWeight: 'bold',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* API Keys Section */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase', fontWeight: 900 }}>API Keys</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          <label htmlFor="gemini-api-key" style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>Gemini API Key:</label>
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <input
              id="gemini-api-key"
              type={showApiKey ? 'text' : 'password'}
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              style={inputStyle}
            />
            <button
              type="button"
              onClick={() => setShowApiKey((v) => !v)}
              aria-pressed={showApiKey}
              style={{
                padding: 'var(--space-md)',
                minHeight: '44px',
                whiteSpace: 'nowrap',
                fontSize: '0.8rem',
              }}
            >
              {showApiKey ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          <label style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>YouTube Client Secrets (JSON):</label>
          <textarea
            value={ytSecrets}
            onChange={(e) => setYtSecrets(e.target.value)}
            style={{ ...inputStyle, minHeight: '150px', fontFamily: 'monospace' }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginTop: 'var(--space-xs)' }}>
            <input 
              type="file" 
              id="file-input"
              accept=".json"
              style={{ display: 'none' }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  const reader = new FileReader();
                  reader.onload = (event) => {
                    try {
                      const parsed = JSON.parse(event.target?.result as string);
                      setYtSecrets(JSON.stringify(parsed, null, 2));
                      updateMutation.mutate({ settings: { youtube_client_secrets: parsed } });
                      setJsonError(false);
                    } catch {
                      setJsonError(true);
                    }
                  };
                  reader.readAsText(file);
                }
              }}
            />
            <label 
              htmlFor="file-input" 
              style={{ 
                padding: 'var(--space-xs) var(--space-sm)',
                border: 'var(--border)',
                fontWeight: 'bold',
                textTransform: 'uppercase',
                cursor: 'pointer',
                background: 'var(--bg)',
                fontSize: '0.8rem',
              }}
            >
              Choose JSON File
            </label>
            <span style={{ fontSize: '0.8rem', opacity: 0.6 }}>
              {settings.youtube_client_secrets ? 'Config loaded successfully' : 'No file selected'}
            </span>
          </div>
          {jsonError && (
            <span style={{ color: 'var(--error)', fontSize: '0.8rem', fontWeight: 'bold', textTransform: 'uppercase', marginTop: 'var(--space-xs)' }}>
              Invalid JSON file content.
            </span>
          )}
        </div>

        {/* The channel itself. The secrets above say which Google project may
            ask; this is the one-time consent that lets it publish. */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)', border: 'var(--border)', padding: 'var(--space-sm)' }}>
          <label style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>YouTube Channel:</label>
          <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>
            {youtube?.connected
              ? `Connected${youtube.account ? ` as ${youtube.account}` : ''}`
              : (youtube?.reason || 'No channel connected.')}
          </span>

          {/* Not an error: uploads work without it. It is the reason a
              thumbnail can be replaced by YouTube's own minutes later. */}
          {youtube?.connected && (youtube.missing_scopes?.length ?? 0) > 0 && (
            <span style={{ fontSize: '0.8rem', color: 'var(--error)', fontWeight: 'bold' }}>
              Missing permission: {youtube.missing_scopes?.join(', ')}. Thumbnails are
              attached on a guess and may be overwritten while YouTube processes the
              video. Reconnect to grant it.
            </span>
          )}

          {youtube?.consent?.pending && (
            <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>
              Waiting for you to finish in the tab that opened. Closed it, or picked the
              wrong account? Press the button for a new one.
            </span>
          )}
          {youtube?.consent?.error && (
            <span style={{ fontSize: '0.8rem', color: 'var(--error)' }}>
              {youtube.consent.error}
            </span>
          )}
          {connectMutation.isError && (
            <span style={{ fontSize: '0.8rem', color: 'var(--error)' }}>
              {(connectMutation.error as Error).message}
            </span>
          )}

          {/* Never disabled by an attempt already waiting: a consent nobody
              finished is exactly when this gets pressed, and the backend gives
              the new one its own window rather than refusing it. */}
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <button
              type="button"
              onClick={() => connectMutation.mutate()}
              disabled={!settings.youtube_client_secrets || connectMutation.isPending}
              style={{
                padding: 'var(--space-xs) var(--space-sm)',
                minHeight: '44px',
                fontWeight: 'bold',
                textTransform: 'uppercase',
                fontSize: '0.8rem',
                alignSelf: 'flex-start',
              }}
            >
              {youtube?.consent?.pending
                ? 'Open Sign-in Again'
                : youtube?.connected ? 'Reconnect Channel' : 'Connect Channel'}
            </button>
            {youtube?.consent?.pending && (
              <button
                type="button"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                style={{
                  padding: 'var(--space-xs) var(--space-sm)',
                  minHeight: '44px',
                  fontWeight: 'bold',
                  textTransform: 'uppercase',
                  fontSize: '0.8rem',
                  alignSelf: 'flex-start',
                }}
              >
                Cancel
              </button>
            )}
          </div>
          {!settings.youtube_client_secrets && (
            <span style={{ fontSize: '0.8rem', opacity: 0.6 }}>
              Add the client secrets above first.
            </span>
          )}
        </div>
      </section>

      {/* Video Defaults Section */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase', fontWeight: 900 }}>Video Defaults</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          <label style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>Resolution:</label>
          <select 
            value={settings.video_defaults?.resolution || 'keep original'}
            onChange={(e) => updateMutation.mutate({ settings: { video_defaults: { ...settings.video_defaults, resolution: e.target.value } } })}
            style={inputStyle}
          >
            <option value="keep original">keep original</option>
            {Object.keys(resolutionsData ?? {}).map(opt => <option key={opt} value={opt}>{opt.toUpperCase()}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          <label style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>Aspect Ratio:</label>
          <select 
            value={settings.video_defaults?.aspect_ratio || 'keep original'}
            onChange={(e) => updateMutation.mutate({ settings: { video_defaults: { ...settings.video_defaults, aspect_ratio: e.target.value } } })}
            style={inputStyle}
          >
            <option value="keep original">keep original</option>
            {Object.keys(aspectRatiosData ?? {}).map(opt => <option key={opt} value={opt}>{opt}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          <label style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>Encoder Codec (e.g. h264_videotoolbox):</label>
          <input
            type="text"
            value={settings.codec || 'libx264'}
            onChange={(e) => updateMutation.mutate({ settings: { codec: e.target.value } })}
            style={inputStyle}
          />
        </div>

        {/* Only the starting point for new projects. Each project keeps its own
            caption settings from then on, styled on its clip pages. */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          <label style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>Captions on new projects:</label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', minHeight: '44px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={Boolean(settings.caption_defaults?.enabled)}
              onChange={(e) => updateMutation.mutate({
                settings: { caption_defaults: { ...settings.caption_defaults, enabled: e.target.checked } },
              })}
              style={{ width: '20px', height: '20px', accentColor: 'var(--accent)' }}
            />
            <span style={{ fontSize: '0.9rem' }}>Burn captions into clips by default</span>
          </label>
          <select
            value={settings.caption_defaults?.preset || 'karaoke_pop'}
            onChange={(e) => updateMutation.mutate({
              settings: { caption_defaults: { ...settings.caption_defaults, preset: e.target.value } },
            })}
            style={inputStyle}
          >
            {Object.entries(captionStyles ?? {}).map(([name, preset]) => (
              <option key={name} value={name}>{preset.label}</option>
            ))}
          </select>
        </div>
      </section>

      {/* YouTube Description Section. Unlike the caption defaults above, these
          are read when a clip is uploaded rather than copied into a project, so
          editing them changes what every existing project publishes. */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase', fontWeight: 900 }}>YouTube Descriptions</h2>
        <p style={{ fontSize: '0.9rem', opacity: 0.8, margin: 0 }}>
          The description every clip is uploaded with. The link back to the original video and any
          text belonging to one project are set on that project's page.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          <label htmlFor="description-global-text" style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>
            Text on every description:
          </label>
          <textarea
            id="description-global-text"
            value={descriptionText}
            onChange={(e) => setDescriptionText(e.target.value)}
            onBlur={() => {
              if (descriptionText === (settings.description_defaults?.text || '')) return;
              saveSettings({
                settings: { description_defaults: { ...settings.description_defaults, text: descriptionText } },
              });
            }}
            placeholder="Subscribe for more, links, credits…"
            style={{ ...inputStyle, minHeight: '90px' }}
          />
          <span style={{ fontSize: '0.8rem', opacity: 0.6 }}>
            Placed wherever the template says {'{global.text}'}.
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          <label htmlFor="description-template" style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>
            Description template:
          </label>
          <textarea
            id="description-template"
            value={descriptionTemplate}
            onChange={(e) => setDescriptionTemplate(e.target.value)}
            onBlur={() => {
              if (descriptionTemplate === (settings.description_defaults?.template || '')) return;
              saveSettings({
                settings: { description_defaults: { ...settings.description_defaults, template: descriptionTemplate } },
              });
            }}
            placeholder={descriptionFields?.default_template}
            style={{ ...inputStyle, minHeight: '180px', fontFamily: 'monospace' }}
          />
          <span style={{ fontSize: '0.8rem', opacity: 0.6 }}>
            Leave empty to use the template shown above. Anything you type is used exactly as
            written; a field in braces is replaced with its value.
          </span>
          <DescriptionFieldHelp />
        </div>
      </section>

      {/* Pipeline Configuration Section */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase', fontWeight: 900 }}>Pipeline Defaults</h2>
        <p style={{ fontSize: '0.9rem', opacity: 0.8, margin: 0 }}>Configure the execution order and auto-run settings for the project pipeline.</p>
        
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {pipelineConfig.execution_order?.map((step: string, index: number) => (
            <div key={step} style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: 'var(--space-md)', 
              padding: 'var(--space-sm) 0',
              borderBottom: 'var(--border)',
            }}>
              <span style={{ width: '24px', fontWeight: 'bold', fontSize: '1rem', opacity: 0.6 }}>{index + 1}.</span>
              <span style={{ flex: 1, fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1px' }}>{step}</span>
              <label style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                fontSize: '0.8rem', 
                fontWeight: 'bold', 
                textTransform: 'uppercase', 
                cursor: 'pointer',
              }}>
                <input 
                  type="checkbox" 
                  checked={pipelineConfig.steps?.[step]?.auto_run || false} 
                  onChange={(e) => {
                    const newConfig = JSON.parse(JSON.stringify(pipelineConfig));
                    newConfig.steps[step].auto_run = e.target.checked;
                    updateMutation.mutate({ 
                      settings: data?.settings || {}, 
                      pipeline_config: newConfig 
                    });
                  }}
                  style={{ cursor: 'pointer' }}
                />
                Auto-run
              </label>
            </div>
          ))}
        </div>
      </section>

    </div>
  );
};
