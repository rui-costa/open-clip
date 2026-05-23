import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Breadcrumbs } from './Breadcrumbs';

describe('Breadcrumbs Component', () => {
  it('renders the list of breadcrumbs', () => {
    const items = [
      { label: 'HOME', onClick: vi.fn() },
      { label: 'PROJECTS', onClick: vi.fn() }
    ];
    render(<Breadcrumbs items={items} />);
    
    expect(screen.getByText(/HOME/i)).toBeDefined();
    expect(screen.getByText(/PROJECTS/i)).toBeDefined();
  });
});
