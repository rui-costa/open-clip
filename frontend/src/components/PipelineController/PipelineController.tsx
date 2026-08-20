import React from 'react';

export type StepStatus = 'todo' | 'running' | 'executed' | 'completed' | 'error' | 'locked';

export interface PipelineStep {
  name: string;
  label: string;
  status: StepStatus;
  // Steps backed by a prompt in backend/config/prompts. They are collapsed
  // behind a single button so adding a prompt does not keep widening the row.
  isLlm?: boolean;
  /** Labels of the steps that must run first, used to explain a locked state. */
  dependsOn?: string[];
}

interface PipelineControllerProps {
  onExecute: (action: 'START' | 'STOP', step: string) => void;
  steps: PipelineStep[];
}

const stepColors = (status: StepStatus) => {
  const isExecuted = status === 'executed' || status === 'completed';
  const isRunning = status === 'running';
  const isError = status === 'error';
  return {
    background: isError ? 'var(--error)' : isExecuted ? 'var(--success)' : isRunning ? 'var(--accent)' : 'var(--bg)',
    color: isError ? 'var(--bg)' : isExecuted ? 'var(--on-success)' : isRunning ? 'var(--bg)' : 'var(--text)',
  };
};

/**
 * The worst status wins, so a failed prompt is visible on the collapsed button
 * without opening the dropdown.
 */
const aggregateStatus = (steps: PipelineStep[]): StepStatus => {
  if (steps.some((s) => s.status === 'error')) return 'error';
  if (steps.some((s) => s.status === 'running')) return 'running';
  if (steps.every((s) => s.status === 'completed' || s.status === 'executed')) return 'completed';
  if (steps.every((s) => s.status === 'locked')) return 'locked';
  return 'todo';
};

/**
 * A touch tap fires pointerenter and often never fires the matching leave, so
 * hover-driven state latches on and stays on. Only a real pointer gets it.
 */
const isHoverPointer = (event: React.PointerEvent) => event.pointerType === 'mouse';

/** The dropdown's own minimum, needed before it has been rendered to measure. */
const MENU_MIN_WIDTH = 240;

const stepButtonStyle = (status: StepStatus, isHovered: boolean): React.CSSProperties => {
  const isLocked = status === 'locked';
  return {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    width: '100%',
    padding: 'var(--space-sm)',
    minHeight: '60px',
    border: 'var(--border)',
    ...stepColors(status),
    opacity: isLocked ? 0.3 : 1,
    cursor: isLocked ? 'not-allowed' : 'pointer',
    transition: 'all 200ms var(--ease-out-quart)',
    position: 'relative',
    overflow: 'hidden',
    boxShadow: isHovered && !isLocked ? '4px 4px 0px var(--border-color)' : 'none',
    textTransform: 'uppercase',
  };
};

const LlmStepMenu: React.FC<{ steps: PipelineStep[]; onExecute: PipelineControllerProps['onExecute'] }> = ({
  steps,
  onExecute,
}) => {
  const [isHovered, setIsHovered] = React.useState(false);
  // Hover is only a preview. Pressing the button pins the dropdown so the rows
  // inside it can actually be reached and clicked.
  const [isPinned, setIsPinned] = React.useState(false);
  // The trigger is a grid cell that can sit anywhere in the row, but the menu
  // is at least MENU_MIN_WIDTH wide. Opened from a cell near the right edge it
  // used to run off the side of the page, so it flips to right-aligned when
  // there is not room to open leftwards.
  const [alignRight, setAlignRight] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const menuRef = React.useRef<HTMLDivElement>(null);
  const menuId = React.useId();

  const status = aggregateStatus(steps);
  const isOpen = isPinned || isHovered;

  const closeAndRefocus = React.useCallback(() => {
    setIsPinned(false);
    triggerRef.current?.focus();
  }, []);

  // Measured in the handler that opens the menu rather than in an effect, so
  // the menu is positioned on the render that first paints it.
  const measureAlignment = React.useCallback(() => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.max(rect.width, MENU_MIN_WIDTH);
    setAlignRight(rect.left + width > document.documentElement.clientWidth);
  }, []);

  React.useEffect(() => {
    if (!isPinned) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setIsPinned(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeAndRefocus();
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [isPinned, closeAndRefocus]);

  // Opening with the keyboard has to land focus inside the menu, otherwise Tab
  // walks past the rows it just opened.
  React.useEffect(() => {
    if (!isPinned) return;
    const first = menuRef.current?.querySelector<HTMLButtonElement>('[role="menuitem"]:not(:disabled)');
    first?.focus();
  }, [isPinned]);

  const runStep = (step: PipelineStep) => {
    if (step.status === 'locked') return;
    onExecute(step.status === 'running' ? 'STOP' : 'START', step.name);
  };

  // `role="menu"` promises arrow-key navigation; a plain list of buttons inside
  // it does not deliver that on its own.
  const onMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(
      menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)') ?? []
    );
    if (items.length === 0) return;
    const current = items.indexOf(document.activeElement as HTMLButtonElement);

    const focusAt = (index: number) => {
      event.preventDefault();
      items[(index + items.length) % items.length].focus();
    };

    switch (event.key) {
      case 'ArrowDown':
        return focusAt(current + 1);
      case 'ArrowUp':
        return focusAt(current - 1);
      case 'Home':
        return focusAt(0);
      case 'End':
        return focusAt(items.length - 1);
      case 'Tab':
        return setIsPinned(false);
    }
  };

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative' }}
      onPointerEnter={(event) => {
        if (!isHoverPointer(event)) return;
        measureAlignment();
        setIsHovered(true);
      }}
      onPointerLeave={(event) => {
        if (!isHoverPointer(event)) return;
        setIsHovered(false);
      }}
    >
      <button
        ref={triggerRef}
        onClick={() => {
          measureAlignment();
          setIsPinned((pinned) => !pinned);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' && !isPinned) {
            event.preventDefault();
            measureAlignment();
            setIsPinned(true);
          }
        }}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={isOpen ? menuId : undefined}
        style={stepButtonStyle(status, isOpen)}
      >
        {/* "LLM Queries" named the implementation. These are the steps where a
            model writes something, which is what the user is choosing between. */}
        <span style={{ fontWeight: 900, fontSize: '1rem', letterSpacing: '0.5px' }}>
          AI Steps {isPinned ? '▲' : '▼'}
        </span>
      </button>

      {isOpen && (
        <div
          id={menuId}
          ref={menuRef}
          role="menu"
          aria-label="AI steps"
          onKeyDown={onMenuKeyDown}
          // Short: a menu is a response to a press, so it should feel like it
          // was already there rather than like it is arriving.
          className="menu-enter"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: alignRight ? 'auto' : 0,
            right: alignRight ? 0 : 'auto',
            minWidth: `max(100%, ${MENU_MIN_WIDTH}px)`,
            // Last resort for a viewport narrower than the menu's own minimum.
            maxWidth: 'calc(100vw - var(--space-xl))',
            zIndex: 20,
            border: 'var(--border)',
            background: 'var(--bg)',
            boxShadow: '4px 4px 0px var(--border-color)',
          }}
        >
          {steps.map((step) => {
            const isLocked = step.status === 'locked';
            return (
              <button
                key={step.name}
                role="menuitem"
                disabled={isLocked}
                onClick={() => runStep(step)}
                style={{
                  display: 'flex',
                  width: '100%',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 'var(--space-md)',
                  padding: 'var(--space-sm)',
                  border: 'none',
                  borderBottom: '2px solid var(--border-color)',
                  background: 'transparent',
                  color: 'var(--text)',
                  cursor: isLocked ? 'not-allowed' : 'pointer',
                  opacity: isLocked ? 0.4 : 1,
                  textTransform: 'uppercase',
                  fontWeight: 700,
                  fontSize: '0.8rem',
                  textAlign: 'left',
                }}
              >
                <span>{step.label}</span>
                <span className="status-badge" style={stepColors(step.status)}>
                  {step.status === 'running' ? 'stop' : statusLabel(step)}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Status is otherwise carried by fill colour alone, which is invisible to a
// colourblind user, in high-contrast mode, and to a screen reader.
const statusLabel = (step: PipelineStep): string => {
  switch (step.status) {
    case 'executed':
    case 'completed':
      return 'done';
    case 'running':
      return 'running — press to stop';
    case 'error':
      return 'failed';
    case 'locked':
      // "Locked" states that the button will not work but not what would make
      // it work, which is the only thing the user can act on.
      return step.dependsOn?.length ? `run ${step.dependsOn.join(' and ')} first` : 'locked';
    default:
      return 'not run';
  }
};

export const PipelineController: React.FC<PipelineControllerProps> = ({ onExecute, steps }) => {
  const [hoveredStep, setHoveredStep] = React.useState<string | null>(null);

  const llmSteps = steps.filter((step) => step.isLlm);
  const anyRunning = steps.some((step) => step.status === 'running');
  const allComplete =
    steps.length > 0 && steps.every((step) => step.status === 'completed' || step.status === 'executed');

  // Same latch as the clip cards: true only when the pipeline finished while
  // this page was open. Reopening a finished project is silent.
  const [wasIncompleteAtMount] = React.useState(() => !allComplete);
  const celebrateComplete = allComplete && wasIncompleteAtMount;
  // The collapsed button takes the slot of the first LLM step, so the row still
  // reads in execution order.
  const firstLlmIndex = steps.findIndex((step) => step.isLlm);

  return (
    <div className="pipeline-controller">
      <div style={{ marginBottom: 'var(--space-md)' }}>
        <button
          onClick={() => onExecute('START', 'all')}
          // A second press while the pipeline runs queues a duplicate run of
          // every step against the same project directory.
          disabled={anyRunning}
          aria-busy={anyRunning}
          style={{
            width: '100%',
            padding: 'var(--space-sm)',
            minHeight: '44px',
            border: 'var(--border)',
            backgroundColor: 'var(--text)',
            color: 'var(--bg)',
            fontWeight: 900,
            fontSize: '1rem',
            textTransform: 'uppercase',
            cursor: anyRunning ? 'not-allowed' : 'pointer',
            opacity: anyRunning ? 0.5 : 1,
            textAlign: 'center',
            transition: 'all 200ms var(--ease-out-quart)',
          }}
        >
          {anyRunning ? 'Pipeline running…' : 'Run full pipeline'}
        </button>
      </div>
      <div className="pipeline-steps" style={{ position: 'relative' }}>
        {/* The whole run landing. Sits under the dropdown's z-index and is
            clipped by its own wrapper, so it cannot bleed over the row or
            trap pointer events. */}
        {celebrateComplete && (
          <span className="sweep-clip" aria-hidden="true">
            <span className="sweep-band sweep-band--success" />
          </span>
        )}
        {steps.map((step, index) => {
          if (step.isLlm) {
            if (index !== firstLlmIndex) return null;
            return <LlmStepMenu key="llm-queries" steps={llmSteps} onExecute={onExecute} />;
          }

          const isRunning = step.status === 'running';
          const isLocked = step.status === 'locked';
          const isHovered = hoveredStep === step.name;

          return (
            <button
              key={step.name}
              disabled={isLocked}
              onClick={() => onExecute(isRunning ? 'STOP' : 'START', step.name)}
              // Pointer-typed: a tap would otherwise leave the hover shadow
              // stuck on the last step touched.
              onPointerEnter={(event) => isHoverPointer(event) && setHoveredStep(step.name)}
              onPointerLeave={(event) => isHoverPointer(event) && setHoveredStep(null)}
              aria-busy={isRunning}
              className={`pipeline-step-btn ${isRunning ? 'pipeline-step-running' : ''} ${step.status === 'executed' || step.status === 'completed' ? 'pipeline-step-success' : ''} ${step.status === 'error' ? 'pipeline-step-error' : ''}`}
              style={stepButtonStyle(step.status, isHovered)}
            >
              <span style={{ fontWeight: 900, fontSize: '1rem', letterSpacing: '0.5px' }}>
                {step.label}
              </span>
              {/* No opacity here. This label is the reason status is not
                  colour-only (see statusLabel), and fading it to 0.85 over the
                  accent fill put it at 3.4:1 — below the threshold it exists
                  to satisfy. */}
              <span style={{ fontWeight: 700, fontSize: '0.65rem', letterSpacing: '0.5px' }}>
                {statusLabel(step)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
