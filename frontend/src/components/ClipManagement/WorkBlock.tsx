import React, { useState } from 'react';

interface WorkBlockProps {
  label: string;
  initialContent: string;
}

export const WorkBlock: React.FC<WorkBlockProps> = ({ label, initialContent }) => {
  const [copied, setCopied] = useState(false);
  const content = initialContent;

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ padding: 'var(--space-sm)', border: '4px solid var(--text)', marginBottom: 'var(--space-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <strong style={{ fontSize: '0.7rem', textTransform: 'uppercase' }}>{label}</strong>
        <button 
          onClick={handleCopy} 
          style={{ padding: '2px 8px', fontSize: '0.6rem', border: '2px solid var(--text)', cursor: 'pointer', background: 'var(--bg)' }}
        >
          {copied ? 'COPIED!' : 'COPY'}
        </button>
      </div>
      <div style={{ padding: '4px', fontSize: '0.85rem', lineHeight: '1.4' }}>
        {content}
      </div>
    </div>
  );
};
