import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ConfirmationModal } from '../ConfirmationModal';
import { Button } from '../Button';
import { uploadClip } from '../../api';
import { Tooltip } from '../Tooltip';

export interface ClipData {
  index: number;
  filename: string;
  original_start: number;
  original_end: number;
  text: string;
}

interface ClipProps {
  projectId: string;
  clip: ClipData;
  onDelete: (index: number) => void;
  onSyncSource: (startTime: number) => void;
  onPauseSource: () => void;
  playingClipIndex: number | null;
  setPlayingClipIndex: (index: number | null) => void;
}

export const Clip: React.FC<ClipProps> = ({ projectId, clip, onDelete, onSyncSource, onPauseSource, playingClipIndex, setPlayingClipIndex }) => {
  const [isConfirming, setIsConfirming] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoSrc = `http://localhost:8000/projects/static/${projectId}/clips/${clip.filename}`;

  useEffect(() => {
    if (playingClipIndex !== null && playingClipIndex !== clip.index) {
      videoRef.current?.pause();
    }
  }, [playingClipIndex]);

  const handleUpload = async () => {
    setIsUploading(true);
    try {
      await uploadClip(projectId, clip.index);
      alert('Upload successful!');
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div style={{ 
      padding: '0', 
      backgroundColor: 'var(--bg)', 
      border: 'var(--border)',
    }}>
      <div style={{ 
        padding: '1rem 1rem 0 1rem',
        marginBottom: '1rem', 
        fontWeight: 900, 
        fontSize: '1.1rem', 
        lineHeight: '1.3', 
        color: 'var(--text)',
        display: '-webkit-box',
        WebkitLineClamp: 3,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        fontStyle: 'italic'
      }}>
        "{clip.text}"
      </div>

      <div style={{ position: 'relative', marginBottom: '1rem', display: 'flex' }}>
        <video 
          ref={videoRef}
          src={videoSrc} 
          controls 
          onPlay={() => {
            setPlayingClipIndex(clip.index);
            onSyncSource(clip.original_start);
          }}
          onPause={() => {
            if (playingClipIndex === clip.index) {
              setPlayingClipIndex(null);
            }
            onPauseSource();
          }}
          style={{ 
            width: '100%', 
            backgroundColor: '#000',
            display: 'block'
          }}
        />
      </div>

      <div style={{ 
        display: 'flex', 
        justifyContent: 'flex-end', 
        gap: 'var(--space-sm)',
        marginTop: '0.5rem',
        padding: '0 1rem 1rem 1rem'
      }}>
        <Tooltip text={isUploading ? "Uploading..." : "Upload to YouTube"}>
          <Button 
            variant="primary"
            onClick={handleUpload}
            disabled={isUploading}
            style={{ 
              padding: '0.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent)',
              borderColor: 'var(--accent)',
              backgroundColor: isUploading ? 'var(--text-muted)' : 'var(--bg)'
            }}
          >
            {isUploading ? '...' : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
            )}
          </Button>
        </Tooltip>

        <Tooltip text="View Details">
          <Button 
            variant="ghost"
            onClick={() => navigate(`/project/${projectId}/clip/${clip.index}`)}
            style={{ 
              padding: '0.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text)',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </Button>
        </Tooltip>

        <Tooltip text="Delete Clip">
          <Button 
            variant="danger"
            onClick={() => setIsConfirming(true)}
            style={{ 
              padding: '0.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--error)',
              borderColor: 'var(--error)'
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </Button>
        </Tooltip>
      </div>


      <ConfirmationModal 
        isOpen={isConfirming}
        title="Delete Clip"
        message={`Are you sure you want to delete this clip? This action cannot be undone.`}
        onConfirm={() => {
          onDelete(clip.index);
          setIsConfirming(false);
        }}
        onCancel={() => setIsConfirming(false)}
      />
    </div>
  );
}

;
