import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ThemeToggle } from './ThemeToggle';

describe('ThemeToggle Component', () => {
  it('calls setTheme when clicked', () => {
    const setTheme = vi.fn();
    render(<ThemeToggle theme="light" setTheme={setTheme} />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    expect(setTheme).toHaveBeenCalled();
  });
});
