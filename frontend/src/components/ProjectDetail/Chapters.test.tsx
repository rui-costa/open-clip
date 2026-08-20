import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChaptersPanel, toChapters, toYouTubeText, parseTimestamp } from './Chapters';

const output = {
  chapters: [
    { chapter_time: '00:01:45', chapter_title: 'Origin story' },
    { chapter_time: '00:00:00', chapter_title: 'Intro' },
    { chapter_time: '00:05:50', chapter_title: 'Red flags' },
  ],
};

describe('chapter formatting', () => {
  it('parses the timestamp forms the model emits', () => {
    expect(parseTimestamp('00:01:45')).toBe(105);
    expect(parseTimestamp('1:45')).toBe(105);
    expect(parseTimestamp('01:02:03')).toBe(3723);
    expect(parseTimestamp('soon')).toBeNull();
    expect(parseTimestamp('')).toBeNull();
  });

  it('sorts by time and renders one YouTube line each', () => {
    expect(toYouTubeText(toChapters(output))).toBe('0:00 Intro\n1:45 Origin story\n5:50 Red flags');
  });

  it('switches every stamp to hours once the video is long', () => {
    const long = { chapters: [{ chapter_time: '00:00:00', chapter_title: 'Intro' }, { chapter_time: '01:02:03', chapter_title: 'Late' }] };

    expect(toYouTubeText(toChapters(long))).toBe('0:00:00 Intro\n1:02:03 Late');
  });

  it('drops unreadable rows instead of failing', () => {
    const broken = { chapters: [{ chapter_time: '00:00:00', chapter_title: 'Intro' }, { chapter_time: 'whenever', chapter_title: 'Broken' }] };

    expect(toChapters(broken)).toHaveLength(1);
  });
});

describe('ChaptersPanel', () => {
  beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });

  it('copies exactly the text YouTube parses', async () => {
    render(<ChaptersPanel projectId="p1" output={output} />);

    fireEvent.click(screen.getByRole('button', { name: /Copy for YouTube/i }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('0:00 Intro\n1:45 Origin story\n5:50 Red flags');
    await waitFor(() => expect(screen.getByRole('button', { name: /Copied/i })).toBeDefined());
  });

  it('warns when the list would not be accepted', () => {
    const late = { chapters: [{ chapter_time: '00:00:30', chapter_title: 'Late start' }] };

    render(<ChaptersPanel projectId="p1" output={late} />);

    const warnings = screen.getAllByRole('alert').map((el) => el.textContent);
    expect(warnings.some((text) => text?.includes('0:00'))).toBe(true);
    expect(warnings.some((text) => text?.includes('at least 3'))).toBe(true);
  });

  it('offers both exports', () => {
    render(<ChaptersPanel projectId="p1" output={output} />);

    expect(screen.getByRole('button', { name: /Download \.txt/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Export Chapter Markers/i })).toBeDefined();
  });
});
