import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { ClipPlayer } from './ClipPlayer';

/**
 * jsdom's HTMLMediaElement has no timeline, so `currentTime` is backed here by
 * a real value. Everything this component does is arithmetic on that value.
 */
let currentTime = 0;

beforeEach(() => {
  currentTime = 0;
  Object.defineProperty(HTMLMediaElement.prototype, 'currentTime', {
    configurable: true,
    get: () => currentTime,
    set: (value: number) => {
      currentTime = value;
    },
  });
  Object.defineProperty(HTMLMediaElement.prototype, 'readyState', { configurable: true, get: () => 1 });
});

const renderPlayer = (start = 30, end = 45) =>
  render(
    <ClipPlayer src="/original.mp4" start={start} end={end} aspectRatio={null} label="a highlight" />
  );

const video = () => document.querySelector('video') as HTMLVideoElement;

describe('ClipPlayer', () => {
  it('opens on the first frame of the window, not the top of the source', () => {
    renderPlayer();
    expect(currentTime).toBe(30);
  });

  it('repeats inside the window instead of running into the next highlight', () => {
    renderPlayer();

    currentTime = 45.2;
    fireEvent.timeUpdate(video());

    expect(currentTime).toBe(30);
  });

  it('snaps back when playback lands before the window', () => {
    renderPlayer();

    currentTime = 12;
    fireEvent.timeUpdate(video());

    expect(currentTime).toBe(30);
  });

  it('scrubs within the window, so the slider cannot reach the rest of the source', () => {
    renderPlayer();

    const slider = screen.getByLabelText(/Position within a highlight/i) as HTMLInputElement;
    expect(slider.max).toBe('15');
    fireEvent.change(slider, { target: { value: '5' } });

    expect(currentTime).toBe(35);
  });

  it('reports the position within the window, not within the source', () => {
    renderPlayer();

    currentTime = 37;
    fireEvent.timeUpdate(video());

    expect(screen.getByText('0:07 / 0:15')).toBeDefined();
  });

  it('re-seeks when a re-run moves the window', () => {
    const { rerender } = renderPlayer();

    rerender(
      <ClipPlayer src="/original.mp4" start={100} end={120} aspectRatio={null} label="a highlight" />
    );

    expect(currentTime).toBe(100);
  });

  it('says so when the source cannot be played, rather than showing a dead frame', () => {
    renderPlayer();

    fireEvent.error(video());

    expect(screen.getByText(/could not be played/i)).toBeDefined();
  });
});
