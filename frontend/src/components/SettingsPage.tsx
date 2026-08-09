import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, type SettingsResponse } from '../api';
import { useDebounce } from '../hooks/useDebounce';

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

  const { data: resolutionsData } = useQuery({
    queryKey: ['resolutions'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8000/resolutions');
      const data = await res.json();
      return Object.keys(data);
    },
  });

  const { data: aspectRatiosData } = useQuery({
    queryKey: ['aspectRatios'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8000/aspect_ratios');
      const data = await res.json();
      return Object.keys(data);
    },
  });

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      queryClient.invalidateQueries({ queryKey: ['pipelineConfig'] });
    },
  });

  const [apiKey, setApiKey] = useState('');
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
      setInitialized(true);
    }
  }, [data]);

  useEffect(() => {
    if (!initialized || !data) return;
    const serverValue = data?.settings?.gemini_api_key || '';
    if (debouncedApiKey !== serverValue) {
      updateMutation.mutate({ settings: { gemini_api_key: debouncedApiKey } });
    }
  }, [debouncedApiKey]);

  useEffect(() => {
    if (!initialized || !data) return;
    const serverValue = data?.settings?.youtube_client_secrets ? JSON.stringify(data.settings.youtube_client_secrets, null, 2) : '';
    if (debouncedYtSecrets !== serverValue) {
      try {
        const parsed = JSON.parse(debouncedYtSecrets);
        updateMutation.mutate({ settings: { youtube_client_secrets: parsed } });
        setJsonError(false);
      } catch (e) {
        setJsonError(true);
      }
    }
  }, [debouncedYtSecrets]);

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
    padding: 'var(--space-xs)',
    background: 'var(--bg)',
    color: 'var(--text)',
    border: 'var(--border)',
    fontFamily: 'inherit',
    outline: 'none',
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
                  padding: 'var(--space-xs) var(--space-sm)',
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
          <label style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>Gemini API Key:</label>
          <input 
            type="text" 
            value={apiKey} 
            onChange={(e) => setApiKey(e.target.value)}
            style={inputStyle}
          />
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
                    } catch (e) {
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
            {resolutionsData?.map(opt => <option key={opt} value={opt}>{opt.toUpperCase()}</option>)}
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
            {aspectRatiosData?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
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

      <div style={{ paddingBottom: 'var(--space-lg)' }}>
        <span style={{ fontSize: '0.8rem', opacity: 0.6, fontWeight: 'bold', textTransform: 'uppercase' }}>
          Automatic synchronization enabled
        </span>
      </div>
    </div>
  );
};
