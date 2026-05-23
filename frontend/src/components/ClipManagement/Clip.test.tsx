import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Clip } from './Clip';
import { describe, it, expect } from 'vitest';

describe('Clip Component', () => {
  const mockClip = {
    index: 0,
    filename: 'clip_000.mp4',
    original_start: 1.0,
    original_end: 3.0,
    text: 'Test clip text'
  };

  it('generates the correct video source URL using projectId', () => {
    const projectId = 'test-project-123';
    render(
      <MemoryRouter>
        <Clip 
          projectId={projectId} 
          clip={mockClip} 
          onDelete={() => {}} 
          onSyncSource={() => {}}
          onPauseSource={() => {}}
          playingClipIndex={null}
          setPlayingClipIndex={() => {}}
        />
      </MemoryRouter>
    );

    const videoElement = document.querySelector('video');
    const expectedSrc = `http://localhost:8000/projects/static/${projectId}/clips/${mockClip.filename}`;
    
    expect(videoElement).toBeDefined();
    expect(videoElement?.getAttribute('src')).toBe(expectedSrc);
  });

  it('renders the clip text and index', () => {
    render(
      <MemoryRouter>
        <Clip 
          projectId="any" 
          clip={mockClip} 
          onDelete={() => {}} 
          onSyncSource={() => {}}
          onPauseSource={() => {}}
          playingClipIndex={null}
          setPlayingClipIndex={() => {}}
        />
      </MemoryRouter>
    );
    
    expect(screen.getByText(/Test clip text/)).toBeDefined();
  });
});
