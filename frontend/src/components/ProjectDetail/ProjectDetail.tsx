import React, { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '../Button';
import { PipelineController } from '../PipelineController/PipelineController';
import type { StepStatus } from '../PipelineController/PipelineController';
import { ClipManager } from '../ClipManagement/ClipManager';
import { getStepStatus as fetchStepStatus } from '../../api';

interface ProjectDetailProps {
  metadata: any;
  pipelineConfig: any;
  activeProcesses: string[];
  onExecuteAction: (action: 'START' | 'STOP', step: string) => void;
  onDeleteClip: (index: number) => void;
  onDeleteProject: () => void;
}

export const ProjectDetail: React.FC<ProjectDetailProps> = ({ metadata, pipelineConfig, activeProcesses, onExecuteAction, onDeleteProject }) => {
  const sourceVideoRef = useRef<HTMLVideoElement>(null);
  const [showMetadata, setShowMetadata] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  const { data: allStatuses } = useQuery({
    queryKey: ['executionStatus', metadata.project_id],
    queryFn: async () => {
      const response = await fetch(`http://localhost:8000/project/${metadata.project_id}/execution_status`);
      return response.json();
    },
    refetchInterval: 2000,
  });

  const { data: currentMetadata, refetch: refetchMetadata } = useQuery({
    queryKey: ['projectMetadata', metadata.project_id],
    queryFn: async () => {
      const response = await fetch(`http://localhost:8000/project/${metadata.project_id}`);
      return response.json();
    },
    initialData: metadata,
    refetchInterval: 2000,
  });

  const displayMetadata = currentMetadata || metadata;

  const steps = (pipelineConfig?.execution_order || []).map((stepName: string) => {
    return {
      name: stepName,
      label: stepName.charAt(0).toUpperCase() + stepName.slice(1),
      status: (allStatuses?.[stepName] as StepStatus) || 'locked'
    };
  });

  const syncSourceVideo = (startTime: number) => {
    if (sourceVideoRef.current) {
      sourceVideoRef.current.muted = true;
      sourceVideoRef.current.currentTime = startTime;
      sourceVideoRef.current.play().catch(err => console.warn("Auto-play prevented:", err));
    }
  };

  const pauseSourceVideo = () => {
    if (sourceVideoRef.current) {
      sourceVideoRef.current.pause();
    }
  };


  const renderMetadata = () => {
    const { highlights } = displayMetadata;

    if (!highlights || highlights.length === 0) {
      return <div style={{ padding: 'var(--space-md)', color: 'var(--text-muted)' }}>No highlights generated yet.</div>;
    }

    const h = highlights[currentIndex];
    // ... rest of renderMetadata remains same
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h4 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-main)' }}>Content Highlights</h4>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{currentIndex + 1} / {highlights.length}</span>
            <Button variant="ghost" onClick={() => setCurrentIndex(prev => Math.max(0, prev - 1))} disabled={currentIndex === 0}>Prev</Button>
            <Button variant="ghost" onClick={() => setCurrentIndex(prev => Math.min(highlights.length - 1, prev + 1))} disabled={currentIndex === highlights.length - 1}>Next</Button>
          </div>
        </div>

        <div style={{ 
          padding: 'var(--space-md)', 
          border: '1px solid var(--border-color)', 
          borderRadius: '12px', 
          background: 'rgba(255, 255, 255, 0.03)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-sm)'
        }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: 'var(--text-accent)' }}>{h.viral_hook_text}</div>
          <div style={{ fontSize: '0.95rem', color: 'var(--text-main)' }}>"{h.highlight_text}"</div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
            {[
              { label: 'X Post', text: h.video_description_for_x },
              { label: 'Reddit', text: h.video_description_for_reddit },
              { label: 'LinkedIn', text: h.video_description_for_linkedin },
            ].map((social) => (
              <div key={social.label} style={{ background: 'rgba(0,0,0,0.2)', padding: 'var(--space-sm)', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>{social.label}</div>
                <div style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>{social.text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="project-detail" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div style={{ 
        display: 'flex', 
        gap: 'var(--space-md)', 
        alignItems: 'flex-start' 
      }}>
        <div style={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column', 
          gap: 'var(--space-md)' 
        }}>
          <div style={{ 
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            paddingBottom: 'var(--space-sm)',
            borderBottom: 'var(--border)',
            marginBottom: 'var(--space-sm)'
          }}>
            <h2 title={`SN: ${displayMetadata.project_id}`} style={{ cursor: 'help', margin: 0 }}>{displayMetadata.name}</h2>
            <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
              <Button
                variant="ghost"
                onClick={() => setShowMetadata(!showMetadata)}
                style={{ fontSize: '0.8rem', padding: '0.5rem 1rem' }}
              >
                {showMetadata ? 'Hide Metadata' : 'View Metadata'}
              </Button>
              <Button 
                variant="danger"
                onClick={onDeleteProject}
                style={{ fontSize: '0.8rem', padding: '0.5rem 1rem' }}
              >
                DELETE PROJECT
              </Button>
            </div>
          </div>

          {showMetadata && (
            <section style={{ marginBottom: 'var(--space-md)' }}>
              {renderMetadata()}
            </section>
          )}

          <section>
            <PipelineController onExecute={onExecuteAction} steps={steps} metadata={displayMetadata} />
          </section>
        </div>

        <div style={{ 
          width: '400px', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: 'var(--space-xs)',
          position: 'sticky',
          top: 'var(--space-md)'
        }}>
          <div style={{ 
            border: 'var(--border)', 
            backgroundColor: '#000',
            lineHeight: 0 
          }}>
            {displayMetadata.files?.original_file ? (
              <video 
                ref={sourceVideoRef}
                src={`http://localhost:8000/projects/static/${displayMetadata.project_id}/${displayMetadata.files.original_file.split('/').pop()}`}
                controls
                style={{ 
                  width: '100%', 
                  display: 'block'
                }}
              />
            ) : (
              <div style={{ padding: '2rem', color: 'white', textAlign: 'center' }}>No original file available</div>
            )}
          </div>
        </div>
      </div>

      <div style={{ borderBottom: 'var(--border)', margin: 'var(--space-md) 0 0 0' }} />

      <section>
        <ClipManager 
          projectId={displayMetadata.project_id} 
          clips={displayMetadata.clips || []} 
          onDeleteClip={onDeleteProject} 
          isLoading={activeProcesses.includes(`${displayMetadata.project_id}_clipper`)}
          onSyncSource={syncSourceVideo}
          onPauseSource={pauseSourceVideo}
        />
      </section>
    </div>
        );
        }
;
