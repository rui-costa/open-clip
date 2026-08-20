import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeAll } from 'vitest';
import { TextOverlay } from './TextOverlay';
import { stubFrameSize } from '../../test/stubFrame';
import { DEFAULT_OVERLAY_TEXT, type OverlayText } from '../../api';

const TITLE: OverlayText = {
  ...DEFAULT_OVERLAY_TEXT,
  text: 'Cold open',
  start: 0,
  duration: 3,
  fade_in: 0.3,
  fade_out: 0.6,
};

// 400px stands in for the rendered preview box; the overlay sizes everything
// from it.
beforeAll(() => stubFrameSize(400));

// The block carrying the fade, one level above the span holding the text.
const block = () => screen.getByText('Cold open').parentElement;

describe('TextOverlay', () => {
  it('ramps the fade in while the clip is playing', () => {
    render(<TextOverlay overlay={TITLE} time={0.15} />);
    // Halfway through a 0.3s fade.
    expect(block()).toHaveStyle({ opacity: '0.5' });
  });

  it('ramps the fade out at the end of the window', () => {
    render(<TextOverlay overlay={TITLE} time={2.7} />);
    // 0.3s of a 0.6s fade-out left. Compared numerically: the ramp is float
    // arithmetic on the playhead, so the exact string is noise.
    expect(Number(block()?.style.opacity)).toBeCloseTo(0.5);
  });

  // The bug this exists for: a paused player sits on the first frame, which is
  // the exact moment the fade-in has ramped to nothing. A saved title drawn at
  // zero opacity is indistinguishable from one that never saved.
  it('draws a stopped picture solid rather than at the start of its fade', () => {
    render(<TextOverlay overlay={TITLE} time={0} still />);
    expect(block()).toHaveStyle({ opacity: '1' });
  });

  it('still draws nothing when the stopped picture is outside the window', () => {
    render(<TextOverlay overlay={TITLE} time={9} still />);
    expect(screen.queryByText('Cold open')).not.toBeInTheDocument();
  });

  // A title a user has not configured a fade for is simply there, playing or
  // not, from the first frame of the clip.
  it('draws a default title solid from the first frame, playing', () => {
    render(<TextOverlay overlay={{ ...DEFAULT_OVERLAY_TEXT, text: 'Cold open' }} time={0} />);
    expect(block()).toHaveStyle({ opacity: '1' });
  });

  it('draws nothing before the title is due', () => {
    render(<TextOverlay overlay={{ ...TITLE, start: 4 }} time={0} />);
    expect(screen.queryByText('Cold open')).not.toBeInTheDocument();
  });

  // What the editor needs: a title being typed has to be on screen even at the
  // frame its own fade starts from.
  it('shows the title regardless of the playhead when asked to', () => {
    render(<TextOverlay overlay={{ ...TITLE, start: 4 }} time={0} forceVisible />);
    expect(block()).toHaveStyle({ opacity: '1' });
  });

  it('anchors the title to the top of the frame, where the burn puts it', () => {
    render(<TextOverlay overlay={{ ...TITLE, position_pct: 12 }} time={0} still />);
    expect(block()).toHaveStyle({ top: '12%' });
  });

  it('sizes the text as a percentage of the frame, not in fixed pixels', () => {
    render(<TextOverlay overlay={{ ...TITLE, font_size_pct: 8 }} time={0} still />);
    // 8% of the 400px frame.
    expect(block()).toHaveStyle({ fontSize: '32px' });
  });

  it('is hidden from assistive technology, which reads the clip text instead', () => {
    const { container } = render(<TextOverlay overlay={TITLE} time={0} still />);
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
  });
});
