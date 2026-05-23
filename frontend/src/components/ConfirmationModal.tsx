import React from 'react';

interface ConfirmationModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  confirmText?: string;
  cancelText?: string;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = 'CONFIRM',
  cancelText = 'CANCEL',
}) => {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(0,0,0,0.8)',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 1000,
      backdropFilter: 'blur(4px)',
      animation: 'fadeIn 200ms var(--ease-out-quart)'
    }}>
      <div style={{
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
        border: 'var(--border)',
        padding: 'var(--space-xl)',
        maxWidth: '500px',
        width: '90%',
        boxShadow: '8px 8px 0px var(--accent)',
        animation: 'entrance 300ms var(--ease-out-quart)'
      }}>
        <h2 style={{ 
          fontSize: '2rem', 
          fontWeight: '900', 
          textTransform: 'uppercase', 
          marginBottom: 'var(--space-md)',
          lineHeight: '1'
        }}>
          {title}
        </h2>
        <p style={{ 
          fontSize: '1.1rem', 
          fontWeight: 'bold', 
          marginBottom: 'var(--space-xl)',
          lineHeight: '1.4'
        }}>
          {message}
        </p>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'flex-end', 
          gap: 'var(--space-md)' 
        }}>
          <button 
            onClick={onCancel}
            style={{
              background: 'transparent',
              border: '4px solid var(--text)',
              color: 'var(--text)',
              fontWeight: 900,
              fontSize: '0.9rem',
              padding: '0.5rem 1.5rem',
              cursor: 'pointer',
              textTransform: 'uppercase',
              transition: 'all 200ms var(--ease-out-quart)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--text)';
              e.currentTarget.style.color = 'var(--bg)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = 'var(--text)';
            }}
          >
            {cancelText}
          </button>
          <button 
            onClick={onConfirm}
            style={{
              background: 'var(--error)',
              border: '4px solid var(--error)',
              color: 'var(--bg)',
              fontWeight: 900,
              fontSize: '0.9rem',
              padding: '0.5rem 1.5rem',
              cursor: 'pointer',
              textTransform: 'uppercase',
              transition: 'all 200ms var(--ease-out-quart)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = 'var(--error)';
              e.currentTarget.style.borderColor = 'var(--error)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--error)';
              e.currentTarget.style.color = 'var(--bg)';
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
