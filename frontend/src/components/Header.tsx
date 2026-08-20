import { Link } from 'react-router-dom';

export function Header() {
  return (
    // Hover lives in CSS behind a pointer guard: set imperatively, the scale
    // stuck after a tap because touch does not reliably send mouseleave.
    <Link to="/" className="wordmark-link">
      <svg width="24" height="24" aria-hidden="true" style={{ transform: 'rotate(-5deg)' }}>
        <use href="/icons.svg#play-icon" />
      </svg>
      <span className="wordmark">OPEN CLIP</span>
    </Link>
  );
}
