import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getProjectMetadata } from '../../api';
import { ClipActions } from './ClipActions';

export const ClipDetail: React.FC = () => {
  const { id: projectId, clipIndex } = useParams<{ id: string; clipIndex: string }>();
  
  const { data: projectMetadata, isLoading, error } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProjectMetadata(projectId!),
    enabled: !!projectId,
  });

  if (isLoading) return <div className="brutalist-card">Loading...</div>;
  if (error) return <div className="brutalist-card">Error loading project</div>;
  if (!projectMetadata) return <div className="brutalist-card">Project not found</div>;

  const clipIndexNum = parseInt(clipIndex || '0');
  const clip = projectMetadata.clips?.[clipIndexNum];
  const highlight = projectMetadata.highlights?.[clipIndexNum];

  if (!clip) return <div className="brutalist-card">Clip not found</div>;

  const videoSrc = `http://localhost:8000/projects/static/${projectId}/clips/${clip.filename}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="brutalist-card" style={{ padding: 'var(--space-md)', border: '4px solid var(--text)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-lg)' }}>
          <section>
            <h2 style={{ fontSize: '1.5rem', marginBottom: 'var(--space-sm)' }}>{highlight?.viral_hook_text || `CLIP ${clipIndexNum + 1}`}</h2>
            <video src={videoSrc} controls style={{ width: '100%', border: '4px solid var(--text)' }} />
            <div style={{ marginTop: 'var(--space-md)', padding: 'var(--space-md)', border: '4px solid var(--text)', backgroundColor: 'var(--bg-secondary)' }}>
              <h3 style={{ margin: '0 0 var(--space-sm) 0', borderBottom: '2px solid var(--text)' }}>TRANSCRIPT</h3>
              <p style={{ margin: 0, fontSize: '0.9rem' }}>{clip.text}</p>
            </div>
          </section>

          <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <h3 style={{ margin: 0 }}>SOCIAL POSTS</h3>
            {highlight ? (
              <>
                {[
                  { label: 'YOUTUBE TITLE', content: highlight.video_title_for_youtube_short },
                  { label: 'TWITTER', content: highlight.video_description_for_x },
                  { label: 'REDDIT', content: highlight.video_description_for_reddit },
                  { label: 'LINKEDIN', content: highlight.video_description_for_linkedin },
                ].map((item, i) => (
                  <div key={i} style={{ padding: 'var(--space-sm)', border: '2px solid var(--text)' }}>
                    <strong style={{ display: 'block', fontSize: '0.7rem', marginBottom: '4px' }}>{item.label}</strong>
                    <p style={{ margin: 0, fontSize: '0.85rem' }}>{item.content}</p>
                  </div>
                ))}
              </>
            ) : (
              <p>No social metadata generated.</p>
            )}
            <ClipActions 
              projectId={projectId!}
              clipIndex={clipIndexNum}
              onRegenerate={() => {}}
              onAddSubtitles={() => {}}
              onAddOverlay={() => {}}
            />
          </section>
        </div>
      </div>
    </div>
  );
};
