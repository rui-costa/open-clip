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
  // Compact is not "the same two blocks with smaller buttons".
  // --------------------------------------------------------------------------
  // It was, and that was the bug: a full-width run bar on a row of its own,
  // then a grid whose 140px minimum track wrapped four steps onto two or three
  // rows — and onto one row each below 600px, where the grid collapses to a
  // single column. The pipeline held half the page against the clip grid it
  // exists to fill.
  describe('compact', () => {
    const renderCompact = () =>
      render(<PipelineController onExecute={vi.fn()} steps={steps} prominence="compact" />);

    it('puts the whole pipeline in one strip, run button included', () => {
      const { container } = renderCompact();

      const strip = container.querySelector('.pipeline-strip');
      expect(strip).not.toBeNull();
      // The grid is gone, not merely restyled.
      expect(container.querySelector('.pipeline-steps')).toBeNull();
      // And the run button is inside the strip rather than on a row above it.
      const runAll = screen.getByRole('button', { name: /Run full pipeline/i });
      expect(runAll.parentElement).toBe(strip);
      expect(runAll.style.width).toBe('auto');
    });

    it('sizes every item in the strip the same, the AI menu included', () => {
      renderCompact();

      // This trigger is built by a different component and was reading the
      // default prominence, so it stood 60px tall in a row of 44px buttons.
      const aiSteps = screen.getByRole('button', { name: /AI Steps/i });
      const step = screen.getByRole('button', { name: /Clipper/i });

      expect(aiSteps.style.minHeight).toBe('44px');
      expect(step.style.minHeight).toBe('44px');
      // Strip items are as wide as their label; grid cells stretch.
      expect(aiSteps.style.width).toBe('auto');
      expect(step.style.width).toBe('auto');
      // One line: the status reads beside the step name, not under it.
      expect(step.style.flexDirection).toBe('row');
    });

    it('leaves the grid alone when the pipeline leads', () => {
      const { container } = render(<PipelineController onExecute={vi.fn()} steps={steps} />);

      expect(container.querySelector('.pipeline-steps')).not.toBeNull();
      expect(container.querySelector('.pipeline-strip')).toBeNull();
      expect(screen.getByRole('button', { name: /Clipper/i }).style.minHeight).toBe('60px');
    });
  });

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
