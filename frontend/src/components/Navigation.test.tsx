import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import { Navigation } from './Navigation';

describe('Navigation Component', () => {
  it('renders the projects link', () => {
    render(
      <MemoryRouter>
        <Navigation onHistoryClick={vi.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByText(/PROJECTS/i)).toBeDefined();
  });
});
