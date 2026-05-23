import React, { useState } from 'react';
import { Clip } from './Clip';
import { ClipSkeleton } from './ClipSkeleton';

interface ClipRaw {
  filename: string;
  original_start: number;
  original_end: number;
  text: string;
}

interface ClipManagerProps {
  projectId: string;
  clips: ClipRaw[];
  onDeleteClip: (index: number) => void;
  isLoading?: boolean;
  onSyncSource: (startTime: number) => void;
  onPauseSource: () => void;
}

export const ClipManager: React.FC<ClipManagerProps> = ({ projectId, clips, onDeleteClip, isLoading, onSyncSource, onPauseSource }) => {
  const [playingClipIndex, setPlayingClipIndex] = useState<number | null>(null);

  if (clips.length === 0 && !isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        padding: 'var(--space-xl)', 
        border: '4px dashed var(--text)', 
        textAlign: 'center',
        backgroundColor: 'var(--bg)' 
      }}>
        <h3 style={{ fontSize: '2rem', fontWeight: 900, margin: '0 0 var(--space-sm) 0', textTransform: 'uppercase' }}>
          No Clips Generated
        </h3>
        <p style={{ fontSize: '1.1rem', maxWidth: '500px', marginBottom: 'var(--space-lg)', lineHeight: '1.4' }}>
          Your extracted clips will appear here once the <strong>Clipper</strong> step of the pipeline is executed.
        </p>
        <div style={{ 
          padding: 'var(--space-sm) var(--space-md)', 
          border: 'var(--border)', 
          fontWeight: 900, 
          fontSize: '1.2rem',
          animation: 'bounce 2s infinite'
        }}>
          ↑ RUN PIPELINE ABOVE
        </div>
        <style>{`
          @keyframes bounce {
            0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
            40% {transform: translateY(-10px);}
            60% {transform: translateY(-5px);}
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="clip-manager">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--space-md)' }}>
        {clips.map((clip, index) => (
          <Clip 
            key={index} 
            projectId={projectId}
            clip={{ ...clip, index }} 
            onDelete={onDeleteClip} 
            onSyncSource={onSyncSource}
            onPauseSource={onPauseSource}
            playingClipIndex={playingClipIndex}
            setPlayingClipIndex={setPlayingClipIndex}
          />
        ))}
        {isLoading && <ClipSkeleton />}
      </div>
    </div>
  );
};
