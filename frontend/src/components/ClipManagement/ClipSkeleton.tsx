import React from 'react';

export const ClipSkeleton: React.FC = () => {
  return (
    <div style={{ 
      padding: '1rem', 
      backgroundColor: '#fff', 
      border: 'var(--border)',
      animation: 'pulse 1.5s ease-in-out infinite'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ 
          width: '60px', 
          height: '1.2rem', 
          backgroundColor: '#eee', 
          borderRadius: '2px' 
        }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ 
            width: '80px', 
            height: '0.85rem', 
            backgroundColor: '#eee', 
            borderRadius: '2px' 
          }} />
          <div style={{ 
            width: '60px', 
            height: '20px', 
            backgroundColor: '#eee', 
            borderRadius: '2px' 
          }} />
        </div>
      </div>

      <div style={{ 
        width: '100%', 
        aspectRatio: '16/9', 
        backgroundColor: '#eee', 
        border: 'var(--border)',
        marginBottom: '1rem' 
      }} />

      <div style={{ marginTop: '0.5rem' }}>
        <div style={{ 
          width: '70px', 
          height: '24px', 
          backgroundColor: '#eee', 
          borderRadius: '2px' 
        }} />
      </div>

      <style>{`
        @keyframes pulse {
          0% { opacity: 0.6; }
          50% { opacity: 1; }
          100% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
};
