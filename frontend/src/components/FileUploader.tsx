import React, { useState, useEffect, useRef } from 'react';
import { PongGame } from './PongGame';

import { getSpinnerVerb } from '../utils/spinnerVerbs';

// ... (remove UPLOAD_VERBS and PROCESSING_VERBS arrays)

interface FileUploaderProps {
  onFileSelect: (file: File) => void;
  isPending: boolean;
  uploadProgress: number;
  /**
   * Creates the project from the chosen file alone. Resolution and aspect
   * ratio are not asked for here: the project starts on the application
   * defaults, and both are changed in Project settings against the clip
   * previews, which is where you can actually see what the choice does.
   */
  onSubmit: () => void;
}

export const FileUploader: React.FC<FileUploaderProps> = ({ onFileSelect, isPending, uploadProgress, onSubmit }) => {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [spinnerVerb, setSpinnerVerb] = useState(getSpinnerVerb());
  const [showGame, setShowGame] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setSpinnerVerb(getSpinnerVerb());
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!isPending) setShowGame(false);
    // Deliberately avoids Space/Enter: those activate whatever control the user
    // currently has focused, so binding them here would swallow every button
    // press on the page for the duration of the upload.
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isPending) return;
      if (e.key === 'p' || e.key === 'P') setShowGame(true);
      if (e.key === 'Escape') setShowGame(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPending]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      onFileSelect(selectedFile);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      setFile(droppedFile);
      onFileSelect(droppedFile);
    }
  };

  // Only the empty dropzone is itself a control. Once a file is chosen the
  // panel contains its own buttons and selects, so it must not also be one.
  const isInteractive = !isPending && !file;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center', 
        padding: 'var(--space-xl)', 
        border: dragActive ? '4px dashed var(--accent)' : '4px dashed var(--text)', 
        textAlign: 'center',
        backgroundColor: 'var(--bg)',
        cursor: isPending ? 'default' : 'pointer',
        transition: 'border 200ms var(--ease-out-quart), transform 200ms var(--ease-out-quart)',
        transform: dragActive ? 'scale(1.01)' : 'scale(1)',
        position: 'relative'
      }}
      onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
      onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => isInteractive && fileInputRef.current?.click()}
      {...(isInteractive ? {
        role: 'button',
        tabIndex: 0,
        'aria-label': 'Choose a video file to upload, or drop one here',
        onKeyDown: (e: React.KeyboardEvent) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        },
      } : {})}
    >
      <input 
        ref={fileInputRef} 
        type="file" 
        accept="video/*" 
        style={{ display: 'none' }} 
        onChange={handleFileChange} 
      />
      
      {isPending ? (
        <div 
          style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center',
            gap: 'var(--space-md)',
            padding: 'var(--space-xl)',
            width: '100%',
            height: '100%',
            zIndex: 1
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ zIndex: 2, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div className="spinner" style={{ 
                width: '60px', 
                height: '60px', 
                border: '6px solid var(--border-color)',
                borderTop: '6px solid var(--accent)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite' 
            }} />
            <h1 style={{ fontSize: '2rem', textTransform: 'uppercase', margin: '10px 0', color: 'var(--text)' }}>
                {spinnerVerb}
            </h1>
            <p style={{ fontSize: '1.2rem', marginBottom: 'var(--space-sm)', color: 'var(--text)' }}>
                {uploadProgress < 99 ? `${uploadProgress}% Complete` : 'Almost finished...'}
            </p>
            {uploadProgress < 99 && (
                <div
                  role="progressbar"
                  aria-valuenow={uploadProgress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Upload progress"
                  style={{ width: '100%', maxWidth: '300px', height: '20px', background: 'var(--bg-secondary)', border: 'var(--border)', overflow: 'hidden' }}
                >
                <div style={{ width: `${uploadProgress}%`, height: '100%', background: 'var(--accent)', transition: 'width 200ms ease-out' }} />
                </div>
            )}
            <p style={{ color: 'var(--text-muted)', marginTop: '10px' }}>
                {uploadProgress < 99 ? 'Uploading heavy file, please do not close this window.' : 'Finalizing project structure...'}
            </p>
            {!showGame && (
                <p style={{ fontSize: '0.9rem', color: 'var(--accent)', fontStyle: 'italic', marginTop: '10px' }}>
                Press P to start Background Pong
                </p>
            )}
          </div>
          {showGame && <PongGame active={isPending} />}
        </div>
      ) : !file ? (
        <>
          <h1 style={{ fontSize: '3rem', fontWeight: 900, margin: '0 0 var(--space-sm) 0', textTransform: 'uppercase' }}>
            Upload Video
          </h1>
          <p style={{ fontSize: '1.2rem', maxWidth: '600px', marginBottom: 'var(--space-lg)', lineHeight: '1.4', fontWeight: 500 }}>
            Drag and drop your video file here, or click to browse your computer. 
            We'll handle the transcription and clipping automatically.
          </p>
          <div style={{ 
            padding: 'var(--space-sm) var(--space-md)', 
            border: 'var(--border)', 
            fontWeight: 900, 
            fontSize: '1.2rem',
            animation: 'nudge 2.4s var(--ease-out-quart) infinite'
          }}>
            DROP VIDEO HERE
          </div>
        </>
      ) : (
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          gap: 'var(--space-md)',
          animation: 'slide-up 400ms var(--ease-out-quart) forwards'
        }}>
          <div style={{ 
            backgroundColor: 'var(--accent)', 
            color: 'var(--bg)', 
            padding: 'var(--space-md)', 
            border: 'var(--border)', 
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 'var(--space-sm)',
            boxShadow: '4px 4px 0px var(--text)'
          }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 900, textTransform: 'uppercase' }}>Selected File</span>
            <h3 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 900 }}>{file.name}</h3>
          </div>
          <p style={{ margin: 0, maxWidth: '420px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            Resolution and aspect ratio are set in <strong>Project settings</strong>, where
            the clip previews show what you are choosing. You can change them at any time.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <button
              disabled={isPending}
              onClick={(e) => { e.stopPropagation(); onSubmit(); }}
              style={{ fontSize: '1.5rem', padding: 'var(--space-md) var(--space-xl)' }}
            >
              CREATE PROJECT
            </button>
            <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', justifyContent: 'center' }}>
              {/* Dropping a second file already replaced the selection, but
                  clicking did nothing once one was chosen. This makes the
                  pointer path match the drag path. */}
              <button
                onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                style={{ fontSize: '0.9rem', minHeight: '44px' }}
              >
                CHOOSE DIFFERENT FILE
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                style={{ fontSize: '0.9rem', minHeight: '44px' }}
              >
                REMOVE FILE
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
