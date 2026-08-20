import React from 'react';

export const ClipSkeleton: React.FC = () => {
  return (
    <div
      role="status"
      aria-label="Generating clip"
      style={{
        padding: 0,
        backgroundColor: 'var(--bg)',
        border: 'var(--border)',
        animation: 'pulse 1.5s ease-in-out infinite'
      }}
    >
      {/* Same shape as a real card, in the same order: picture, then the two
          lines of quote, then the action row. A skeleton laid out differently
          from what replaces it reshuffles the grid the moment it does. */}
      <div
        className="skeleton-block"
        style={{
          width: '100%',
          aspectRatio: '16/9',
          maxHeight: '320px'
        }}
      />

      <div style={{ padding: 'var(--space-md) var(--space-md) 0 var(--space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
        <div className="skeleton-block" style={{ width: '100%', height: '0.85rem' }} />
        <div className="skeleton-block" style={{ width: '65%', height: '0.85rem' }} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', padding: 'var(--space-sm) var(--space-md) var(--space-md) var(--space-md)' }}>
        <div className="skeleton-block" style={{ width: '44px', height: '44px' }} />
        <div className="skeleton-block" style={{ width: '44px', height: '44px' }} />
      </div>
    </div>
  );
};
