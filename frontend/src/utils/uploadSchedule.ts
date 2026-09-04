/**
 * The words a schedule is described in, shared by every place that describes
 * one: the application defaults in Settings, and the projects that disagree
 * with them, for the YouTube upload and the Postiz import alike.
 *
 * All four offer the same days, the same hours and the same "how many a day".
 * A project whose options read differently from the default it is following is
 * a project the user cannot compare against anything — and two platforms whose
 * options read differently are one set of clips on two calendars.
 */

/**
 * How far ahead a schedule may be set, in years.
 *
 * There is no technical limit — YouTube takes any future time — so this is a
 * judgement about what a date field is for: a year typed digit by digit passes
 * through 0002 and 0202 on its way to 2026, and a field that accepts those
 * accepts the typo as readily as the date. Two years is well past any run of
 * clips anybody is planning and short enough to catch a slipped keystroke.
 */
export const MAX_SCHEDULE_YEARS_AHEAD = 2;

/** A day as a date input writes it, on the reader's own clock rather than UTC. */
export const toISODate = (day: Date): string =>
  `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;

/** The first day a schedule may begin: today. Yesterday is already gone. */
export const earliestScheduleDate = (): string => toISODate(new Date());

/** The last day a schedule may begin. */
export const latestScheduleDate = (): string => {
  const day = new Date();
  day.setFullYear(day.getFullYear() + MAX_SCHEDULE_YEARS_AHEAD);
  return toISODate(day);
};

/** Every hour of the day, as a select offers them. */
export const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

/** One hour, written the way a clock writes it. */
export const hourLabel = (hour: number): string => `${String(hour).padStart(2, '0')}:00`;

/** How many clips a day a schedule may publish. 0 is all of them at once. */
export const PER_DAY_CHOICES: { value: number; label: string }[] = [
  // Zero first because it is the default, and because "everything at nine on
  // Friday" is a schedule somebody wants rather than an absence of one.
  { value: 0, label: 'All at the same moment' },
  { value: 1, label: '1 per day' },
  { value: 2, label: '2 per day' },
  { value: 3, label: '3 per day' },
  { value: 4, label: '4 per day' },
  { value: 6, label: '6 per day' },
];

/** What each privacy is called where a user picks one. */
export const PRIVACY_LABELS: Record<string, string> = {
  // Private first, and the default: the only one of the four that cannot reach
  // an audience by accident.
  private: 'Private — only you',
  unlisted: 'Unlisted — anyone with the link',
  public: 'Public — live immediately',
  schedule: 'Scheduled — public at a time you pick',
};

/**
 * A published clip's own publish time, written for a person.
 *
 * Read back from what YouTube was told, which is UTC, and shown on the reader's
 * own clock — the same clock the hours were picked on.
 */
export const formatPublishAt = (iso: string): string => {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;
  return when.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};
