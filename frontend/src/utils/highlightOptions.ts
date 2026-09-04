import type { HighlightProjectSettings } from '../api';

/**
 * What a highlights run asks for when nobody has said otherwise.
 *
 * The same numbers `backend/src/services/highlight_options.py` falls back to —
 * the ones the prompt used to carry in its own text. They are repeated here so
 * a field can say what it would do if left empty, which is the one thing an
 * empty field cannot say for itself. The backend stays the authority: nothing
 * here is ever sent as a value, only shown as a label.
 */
export const SHIPPED_HIGHLIGHT_DEFAULTS = {
  min_clips: 7,
  max_clips: 12,
  min_duration: 18,
  max_duration: 110,
} as const;

/** The widest a field accepts, matching the backend's own bounds. */
export const MAX_HIGHLIGHT_CLIPS = 100;
export const MAX_HIGHLIGHT_DURATION = 3600;

export type HighlightNumberField = keyof typeof SHIPPED_HIGHLIGHT_DEFAULTS;

/**
 * What this project would actually ask for: its own answer, the application's,
 * then the shipped one.
 *
 * Mirrors the backend's resolution rather than guessing at it, so a hint under
 * an empty field names the number the run will really use.
 */
export const effectiveHighlight = (
  field: HighlightNumberField,
  project: Partial<HighlightProjectSettings> | undefined,
  app: Partial<HighlightProjectSettings> | undefined
): number => {
  const own = project?.[field];
  if (typeof own === 'number') return own;
  const application = app?.[field];
  if (typeof application === 'number') return application;
  return SHIPPED_HIGHLIGHT_DEFAULTS[field];
};

/** Seconds as they read in a sentence: `20`, not `20.0`. */
export const formatSeconds = (value: number): string =>
  Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
