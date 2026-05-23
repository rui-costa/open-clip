import { useNavigate } from 'react-router-dom';

export function Header() {
  const navigate = useNavigate();
  return (
    <div 
      style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 'var(--space-sm)',
        cursor: 'pointer',
        transition: 'transform 0.2s ease-out'
      }}
      onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
      onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
      onClick={() => navigate('/')}
    >
      <svg width="24" height="24" style={{ transform: 'rotate(-5deg)', transition: 'transform 0.3s ease' }}>
        <use href="/icons.svg#play-icon" />
      </svg>
      <h1 style={{ fontSize: 'clamp(2rem, 5vw, 4rem)' }}>OPEN CLIP</h1>
    </div>
  );
}
