import React from 'react';
import { Button } from './Button';

interface NavButtonProps {
  onClick: () => void;
  children: React.ReactNode;
}

export const NavButton: React.FC<NavButtonProps> = ({ onClick, children }) => (
  <Button variant="ghost" onClick={onClick} style={{ marginRight: 'var(--space-sm)' }}>
    {children}
  </Button>
);
