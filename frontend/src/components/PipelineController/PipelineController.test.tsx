import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PipelineController } from './PipelineController';
import type { PipelineStep } from './PipelineController';

const steps: PipelineStep[] = [
  { name: 'transcription', label: 'Transcription', status: 'completed' },
  { name: 'highlights', label: 'Highlights', status: 'completed', isLlm: true },
  { name: 'chapters', label: 'Chapters', status: 'error', isLlm: true },
  { name: 'clipper', label: 'Clipper', status: 'todo' },
];

const renderController = (onExecute = vi.fn()) => {
  render(<PipelineController onExecute={onExecute} steps={steps} />);
  return onExecute;
};

describe('PipelineController', () => {
  it('collapses every LLM step into a single button', () => {
    renderController();

    expect(screen.getByRole('button', { name: /AI Steps/i })).toBeDefined();
    expect(screen.queryByRole('button', { name: /^Highlights$/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Chapters$/i })).toBeNull();
  });

  it('previews the queries and their status on hover', () => {
    renderController();
    const trigger = screen.getByRole('button', { name: /AI Steps/i });

    expect(screen.queryByRole('menu')).toBeNull();
    fireEvent.pointerEnter(trigger.parentElement!, { pointerType: 'mouse' });

    const menu = screen.getByRole('menu');
    expect(menu.textContent).toContain('Highlights');
    // The rows carry the same human labels as the step buttons, not the raw
    // status strings from the API.
    expect(menu.textContent).toContain('done');
    expect(menu.textContent).toContain('failed');
  });

  it('ignores hover from a touch pointer, which never sends the matching leave', () => {
    renderController();
    const trigger = screen.getByRole('button', { name: /AI Steps/i });

    fireEvent.pointerEnter(trigger.parentElement!, { pointerType: 'touch' });

    // A tap opens the menu through the click handler instead, so opening here
    // as well would leave it latched open with no way to dismiss it by hand.
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('keeps the dropdown open once pressed so its rows can be clicked', () => {
    const onExecute = renderController();
    const trigger = screen.getByRole('button', { name: /AI Steps/i });

    fireEvent.click(trigger);
    // Pointer leaves the button on the way to a row; the pinned menu must survive it.
    fireEvent.pointerLeave(trigger.parentElement!, { pointerType: 'mouse' });

    fireEvent.click(screen.getByRole('menuitem', { name: /Chapters/i }));
    expect(onExecute).toHaveBeenCalledWith('START', 'chapters');
  });

  describe('completion flourish', () => {
    const allDone: PipelineStep[] = steps.map((step) => ({ ...step, status: 'completed' }));

    it('stays silent for a pipeline that was already finished on arrival', () => {
      render(<PipelineController onExecute={vi.fn()} steps={allDone} />);
      expect(document.querySelector('.sweep-clip')).toBeNull();
    });

    it('sweeps when the last step completes while the page is open', () => {
      const { rerender } = render(<PipelineController onExecute={vi.fn()} steps={steps} />);
      expect(document.querySelector('.sweep-clip')).toBeNull();

      rerender(<PipelineController onExecute={vi.fn()} steps={allDone} />);
      expect(document.querySelector('.sweep-clip')).not.toBeNull();
    });
  });

  it('surfaces a failed query on the collapsed button', () => {
    renderController();

    // `chapters` errored, so the aggregate must not read as completed.
    expect(screen.getByRole('button', { name: /AI Steps/i }).style.background).toBe('var(--error)');
  });
});
