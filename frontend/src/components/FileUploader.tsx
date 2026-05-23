import React, { useState, useRef } from 'react';

interface FileUploaderProps {
  onFileSelect: (file: File) => void;
  isPending: boolean;
  onSubmit: () => void;
}

export const FileUploader: React.FC<FileUploaderProps> = ({ onFileSelect, isPending, onSubmit }) => {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        cursor: 'pointer',
        transition: 'border 200ms var(--ease-out-quart), transform 200ms var(--ease-out-quart)',
        transform: dragActive ? 'scale(1.01)' : 'scale(1)',
      }}
      onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
      onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
    >
      <input 
        ref={fileInputRef} 
        type="file" 
        accept="video/*" 
        style={{ display: 'none' }} 
        onChange={handleFileChange} 
      />
      
      {!file ? (
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
              {isPending ? 'CREATING PROJECT...' : 'CREATE PROJECT'}
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
