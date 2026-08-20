import { NavButton } from './NavButton';
import { useNavigate } from 'react-router-dom';

interface NavigationProps {
  onHistoryClick: () => void;
}

export function Navigation({ onHistoryClick }: NavigationProps) {
  const navigate = useNavigate();
  return (
    // Labelled because Breadcrumbs renders a second <nav>; two unnamed
    // navigation landmarks are indistinguishable in a screen reader's list.
    <nav
      aria-label="Primary"
      style={{
        display: 'flex',
        gap: 'var(--space-sm)',
        alignItems: 'center'
      }}
    >
      <NavButton onClick={onHistoryClick}>PROJECTS</NavButton>
      <NavButton onClick={() => navigate('/settings')}>SETTINGS</NavButton>
    </nav>
  );
}
