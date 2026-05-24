import React, { useState, useEffect, useRef } from 'react';
import { PongGame } from './PongGame';

const UPLOAD_VERBS = [
  "Uploading...",
  "Moving data...",
  "Securing packets...",
  "Transferring...",
  "Writing to disk..."
];

const PROCESSING_VERBS = [
  "Transcribing...",
  "Analyzing Audio...",
  "Extracting Highlights...",
  "Generating Clips...",
  "Finalizing Project..."
];

interface FileUploaderProps {
  onFileSelect: (file: File) => void;
  isPending: boolean;
  uploadProgress: number;
  onSubmit: () => void;
}

export const FileUploader: React.FC<FileUploaderProps> = ({ onFileSelect, isPending, uploadProgress, onSubmit }) => {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [verbIndex, setVerbIndex] = useState(0);
  const [showGame, setShowGame] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setVerbIndex((prev) => (prev + 1) % (uploadProgress < 100 ? UPLOAD_VERBS.length : PROCESSING_VERBS.length));
    }, 2500);
    return () => clearInterval(interval);
  }, [uploadProgress]);

  useEffect(() => {
    if (!isPending) setShowGame(false);
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isPending && [' ', 'Enter'].includes(e.key)) {
        setShowGame(true);
      }
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
      onClick={() => !isPending && fileInputRef.current?.click()}
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
                border: '6px solid var(--border)', 
                borderTop: '6px solid var(--accent)', 
                borderRadius: '50%',
                animation: 'spin 1s linear infinite' 
            }} />
            <h2 style={{ fontSize: '2rem', textTransform: 'uppercase', margin: '10px 0', color: 'var(--text)' }}>
                {uploadProgress < 100 ? UPLOAD_VERBS[verbIndex] : PROCESSING_VERBS[verbIndex]}
            </h2>
            <p style={{ fontSize: '1.2rem', marginBottom: 'var(--space-sm)', color: 'var(--text)' }}>
                {uploadProgress < 100 ? `${uploadProgress}% Complete` : 'Processing...'}
            </p>
            {uploadProgress < 100 && (
                <div style={{ width: '300px', height: '20px', background: 'var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
                <div style={{ width: `${uploadProgress}%`, height: '100%', background: 'var(--accent)', transition: 'width 200ms ease-out' }} />
                </div>
            )}
            <p style={{ color: 'var(--text-muted)', marginTop: '10px' }}>
                {uploadProgress < 100 ? 'Uploading heavy file, please do not close this window.' : 'Backend processing in progress.'}
            </p>
            {!showGame && (
                <p style={{ fontSize: '0.9rem', color: 'var(--accent)', fontStyle: 'italic', marginTop: '10px' }}>
                Press Space to start Background Pong
                </p>
            )}
          </div>
          {showGame && <PongGame active={isPending} />}
        </div>
      ) : !file ? (
        <>
          <h2 style={{ fontSize: '3rem', fontWeight: 900, margin: '0 0 var(--space-sm) 0', textTransform: 'uppercase' }}>
            Upload Video
          </h2>
          <p style={{ fontSize: '1.2rem', maxWidth: '600px', marginBottom: 'var(--space-lg)', lineHeight: '1.4', fontWeight: 500 }}>
            Drag and drop your video file here, or click to browse your computer. 
            We'll handle the transcription and clipping automatically.
          </p>
          <div style={{ 
            padding: 'var(--space-sm) var(--space-md)', 
            border: 'var(--border)', 
            fontWeight: 900, 
            fontSize: '1.2rem',
            animation: 'bounce 2s infinite'
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
          animation: 'slideUp 400ms var(--ease-out-quart) forwards' 
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
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <button 
              disabled={isPending} 
              onClick={(e) => { e.stopPropagation(); onSubmit(); }}
              style={{ fontSize: '1.5rem', padding: 'var(--space-md) var(--space-xl)' }}
            >
              CREATE PROJECT
            </button>
            <button 
              onClick={(e) => { e.stopPropagation(); setFile(null); }} 
              style={{ 
                fontSize: '0.9rem', 
                opacity: 1 
              }}
            >
              REMOVE FILE
            </button>
          </div>
        </div>
      )}
      <style>{`
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes bounce {
          0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
          40% {transform: translateY(-10px);}
          60% {transform: translateY(-5px);}
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
};
