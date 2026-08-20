import React, { useEffect, useRef, useState } from 'react';

interface WorkBlockProps {
  label: string;
  initialContent: string;
}

export const WorkBlock: React.FC<WorkBlockProps> = ({ label, initialContent }) => {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const content = initialContent;

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const handleCopy = async () => {
    try {
      // Absent over plain HTTP and rejected when the document is not focused,
      // so this is not a safe call to make bare. The unhandled rejection used
      // to leave the button claiming "COPIED!" with nothing on the clipboard.
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(content);
      setCopyState('copied');
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopyState('idle'), 2000);
    } catch (err) {
      console.warn('Clipboard write failed', err);
      setCopyState('failed');
    }
  };

  return (
    <div style={{ padding: 'var(--space-sm)', border: 'var(--border)', marginBottom: 'var(--space-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
        <strong style={{ fontSize: '0.7rem', textTransform: 'uppercase' }}>{label}</strong>
        <button
          onClick={handleCopy}
          style={{ padding: '2px 8px', fontSize: '0.6rem', minHeight: '44px', border: '2px solid var(--border-color)', cursor: 'pointer', background: 'var(--bg)', flexShrink: 0 }}
        >
          {copyState === 'copied' ? 'COPIED!' : copyState === 'failed' ? 'COPY FAILED' : 'COPY'}
        </button>
      </div>
      {copyState === 'failed' && (
        <p role="alert" style={{ margin: '0 0 var(--space-sm) 0', fontSize: '0.7rem', color: 'var(--error)' }}>
          Could not reach the clipboard. Select the text below and copy it manually.
        </p>
      )}
      <div style={{ padding: 'var(--space-sm)', fontSize: '0.85rem', lineHeight: '1.4' }}>
        {content}
      </div>
    </div>
  );
};
