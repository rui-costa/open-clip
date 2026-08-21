import React from 'react';
import { Button } from '../Button';
import { LlmOutputs } from './LlmOutputs';
import type { Highlight } from '../../api';

interface HighlightPanelProps {
  projectId: string;
  highlights: Highlight[] | undefined;
  /** Output of prompt-defined LLM tasks, rendered under the highlight. */
  llmOutputs: Record<string, unknown>;
  /** Which highlight is on show. Clamped here, not by the caller. */
  index: number;
  /** Which way the last page went, so the panel enters from that side. */
  swapDirection: 1 | -1;
  onPage: (direction: 1 | -1, nextIndex: number) => void;
}

/**
 * What the AI Output panel shows: one highlight at a time, plus every
 * prompt-defined task's output under it.
 *
 * Its own component, and memoised, because the page around it re-renders twice
 * a second for as long as a step is running. Inline, this was a function call
 * in the middle of that render — so a project with a 200-row output table
 * rebuilt all 200 rows on every poll tick, for a panel whose contents change
 * when the model writes, which is a handful of times per project.
 */
const HighlightPanelBody: React.FC<HighlightPanelProps> = ({
  projectId,
  highlights,
  llmOutputs,
  index: requestedIndex,
  swapDirection,
  onPage,
}) => {
  // Prompt-defined tasks have no bespoke view, so they are rendered
  // generically alongside the highlights.
  const outputs = <LlmOutputs projectId={projectId} outputs={llmOutputs} />;

  if (!highlights || highlights.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        {/* An empty panel should say which step fills it, not just that it
            is empty. */}
        <div style={{ padding: 'var(--space-md)', color: 'var(--text-muted)' }}>
          No highlights yet. Run the Highlights step to pick out the moments worth clipping.
        </div>
        {outputs}
      </div>
    );
  }

  // A re-run can return fewer highlights than the last one, leaving the
  // index pointing past the end of the new list.
  const index = Math.min(requestedIndex, highlights.length - 1);
  const h = highlights[index];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-main)' }}>Content Highlights</h2>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{index + 1} / {highlights.length}</span>
          <Button variant="ghost" onClick={() => onPage(-1, Math.max(0, index - 1))} disabled={index === 0}>
            Prev
          </Button>
          <Button
            variant="ghost"
            onClick={() => onPage(1, Math.min(highlights.length - 1, index + 1))}
            disabled={index === highlights.length - 1}
          >
            Next
          </Button>
        </div>
      </div>

      {/* Prev/Next replaces the whole panel, so the swap has to be announced.
          The announcement is this one sentence rather than the panel itself:
          an aria-live region around the panel re-read the hook, the quote and
          all three social posts on every press, and again on every background
          metadata refresh. */}
      <p className="visually-hidden" role="status" aria-live="polite">
        Highlight {index + 1} of {highlights.length}
        {h.viral_hook_text ? `: ${h.viral_hook_text}` : ''}
      </p>

      <div
        // Keyed on the index so React remounts the panel and the entrance
        // replays on every page, rather than only the first.
        key={index}
        className="highlight-swap"
        style={{
          ['--swap-from' as string]: swapDirection > 0 ? '12px' : '-12px',
          padding: 'var(--space-md)',
          border: 'var(--border)',
          background: 'var(--bg)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-sm)',
          // Model output is arbitrary text: a URL or an unspaced CJK run has
          // no break opportunity and would otherwise widen the whole page.
          overflowWrap: 'anywhere',
        }}
      >
        <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: 'var(--text-accent)' }}>
          {h.viral_hook_text || `Highlight ${index + 1}`}
        </div>
        {h.highlight_text && <div style={{ fontSize: '0.95rem', color: 'var(--text-main)' }}>"{h.highlight_text}"</div>}

        {/* Flat columns under a rule, not boxes. These sit inside the
            bordered highlight panel, so giving each one its own border made
            a card inside a card — the one nesting DESIGN.md rules out. */}
        <div className="social-grid" style={{ marginTop: 'var(--space-sm)' }}>
          {[
            { label: 'X Post', text: h.video_description_for_x },
            { label: 'Reddit', text: h.video_description_for_reddit },
            { label: 'LinkedIn', text: h.video_description_for_linkedin },
          ].map((social) => (
            <div
              key={social.label}
              style={{
                // Accent, where the quote above keeps the neutral rule. The
                // hook at the top of this panel has been accent for the same
                // reason since it was written: it is the model talking, not
                // the video. The quote is the one thing here that was actually
                // said, so it is the one thing that stays black.
                borderTop: 'var(--border-width) solid var(--accent)',
                paddingTop: 'var(--space-sm)',
                minWidth: 0,
              }}
            >
              <div style={{ fontSize: '0.65rem', fontWeight: 900, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 'var(--space-sm)' }}>{social.label}</div>
              <div style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>
                {social.text || <span style={{ color: 'var(--text-muted)' }}>No post for this platform.</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {outputs}
    </div>
  );
};

export const HighlightPanel = React.memo(HighlightPanelBody);
