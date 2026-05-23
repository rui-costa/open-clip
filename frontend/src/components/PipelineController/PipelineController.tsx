import React from 'react';

export type StepStatus = 'todo' | 'running' | 'executed' | 'locked';

export interface PipelineStep {
  name: string;
  label: string;
  status: StepStatus;
}

interface PipelineControllerProps {
  onExecute: (action: 'START' | 'STOP', step: string) => void;
  steps: PipelineStep[];
  metadata?: any;
}

export const PipelineController: React.FC<PipelineControllerProps> = ({ onExecute, steps, metadata }) => {
  const [hoveredStep, setHoveredStep] = React.useState<string | null>(null);
  const currentClipCount = metadata?.clips?.length || 0;
  const totalClips = metadata?.components?.total_expected_clips || null;

  return (
    <div className="pipeline-controller">
      <div style={{ marginBottom: 'var(--space-md)' }}>
        <button
          onClick={() => onExecute('START', 'all')}
          style={{
            width: '100%',
            padding: 'var(--space-sm)',
            border: '4px solid var(--text)',
            backgroundColor: 'var(--text)',
            color: 'var(--bg)',
            fontWeight: 900,
            fontSize: '1rem',
            textTransform: 'uppercase',
            cursor: 'pointer',
            textAlign: 'center',
            transition: 'all 200ms var(--ease-out-quart)',
          }}
        >
          RUN FULL PIPELINE 🚀
        </button>
      </div>
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', 
        gap: 'var(--space-md)', 
        paddingBottom: 'var(--space-sm)'
      }}>
        {steps.map((step) => {
          const isExecuted = step.status === 'executed';
          const isRunning = step.status === 'running';
          const isLocked = step.status === 'locked';
          const isHovered = hoveredStep === step.name;

          return (
            <button
              key={`${step.name}-${step.status}`}
              disabled={isLocked}
              onClick={() => onExecute(isRunning ? 'STOP' : 'START', step.name)}
              onMouseEnter={() => setHoveredStep(step.name)}
              onMouseLeave={() => setHoveredStep(null)}
              className={`pipeline-step-btn ${isRunning ? 'pipeline-step-running' : ''} ${isExecuted ? 'pipeline-step-success' : ''}`}
              style={{ 
                display: 'flex', 
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
                padding: 'var(--space-sm)', 
                minHeight: '60px',
                border: '4px solid var(--text)',
                backgroundColor: isExecuted ? 'var(--success)' : (isRunning ? 'var(--accent)' : 'var(--bg)'),
                color: isExecuted ? 'var(--text)' : (isRunning ? 'var(--bg)' : 'var(--text)'),
                opacity: isLocked ? 0.3 : 1,
                cursor: isLocked ? 'not-allowed' : 'pointer',
                transition: 'all 200ms var(--ease-out-quart)',
                position: 'relative',
                overflow: 'hidden',
                boxShadow: (isHovered && !isLocked) ? '4px 4px 0px var(--text)' : 'none',
                textTransform: 'uppercase',
              }}
            >
              <span style={{ fontWeight: 900, fontSize: '1rem', letterSpacing: '0.5px' }}>
                {step.label}
              </span>
              {isRunning && step.name === 'clipper' && (
                <div style={{ fontSize: '0.7rem', marginTop: '4px', fontWeight: 700, opacity: 0.9, textTransform: 'none' }}>
                  {totalClips 
                    ? (currentClipCount < totalClips 
                        ? `Clip ${currentClipCount + 1} of ${totalClips}` 
                        : `Finalizing...`) 
                    : `Clip ${currentClipCount + 1}...`}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
