import React, { useState } from 'react';
import { uploadClip } from '../../api';

interface ClipActionsProps {
  projectId: string;
  clipIndex: number;
  onRegenerate: () => void;
  onAddSubtitles: () => void;
  onAddOverlay: () => void;
}

export const ClipActions: React.FC<ClipActionsProps> = ({ 
  projectId,
  clipIndex,
  onRegenerate, 
  onAddSubtitles, 
  onAddOverlay 
}) => {
  const [isUploading, setIsUploading] = useState(false);

  const handleUpload = async () => {
    setIsUploading(true);
    try {
      await uploadClip(projectId, clipIndex);
      alert('Upload successful!');
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please check logs.');
    } finally {
      setIsUploading(false);
    }
  };

  const buttonStyle = {
    padding: 'var(--space-sm)',
    border: '2px solid var(--text)',
    background: 'var(--bg)',
    color: 'var(--text)',
    cursor: isUploading ? 'not-allowed' : 'pointer',
    textTransform: 'uppercase',
    fontWeight: 900,
    fontSize: '0.75rem',
    width: '100%',
    textAlign: 'left' as const,
    boxShadow: '2px 2px 0px var(--text)',
    transition: 'all 200ms var(--ease-out-quart)',
    opacity: isUploading ? 0.5 : 1
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
      <h4 style={{ margin: '0 0 var(--space-sm) 0', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Actions</h4>
      <button style={buttonStyle} onClick={handleUpload} disabled={isUploading}>
        {isUploading ? 'Uploading...' : 'Upload to YouTube'}
      </button>
      <button style={buttonStyle} onClick={onRegenerate}>Regenerate Clip</button>
      <button style={buttonStyle} onClick={onAddSubtitles}>Add Subtitles (Beta)</button>
      <button style={buttonStyle} onClick={onAddOverlay}>Add Overlay Text (Beta)</button>
    </div>
  );
};
