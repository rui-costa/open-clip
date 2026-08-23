import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DateField } from './DateField';

/** jsdom gives a date input no role, so it is addressed by its id. */
const dateInput = () => document.getElementById('d') as HTMLInputElement;

// `focusIn`, not `focus`: React listens for focusin, and a plain focus event
// never reaches onFocus — so the field would be asserted on as though nobody
// had ever put a cursor in it.

/** The bounds the schedule fields use, fixed so the tests do not drift. */
const MIN = '2026-08-23';
const MAX = '2028-08-23';

const field = (value: string, onCommit = vi.fn()) => {
  const view = render(
    <DateField id="d" value={value} onCommit={onCommit} min={MIN} max={MAX} />
  );
  return { onCommit, ...view };
};

describe('DateField', () => {
  it('saves a whole day as soon as one is picked', () => {
    const { onCommit } = field('');

    fireEvent.focusIn(dateInput());
    fireEvent.change(dateInput(), { target: { value: '2026-09-01' } });

    expect(onCommit).toHaveBeenCalledWith('2026-09-01');
  });

  // The bug this field exists for: a date input reads empty until all three
  // segments are filled, so saving on change stored "no date" on the first
  // digit of the year — and the refetch rewrote the input under the cursor.
  it('saves nothing while a day is only half typed', () => {
    const { onCommit } = field('2026-09-01');

    fireEvent.focusIn(dateInput());
    fireEvent.change(dateInput(), { target: { value: '' } });

    expect(onCommit).not.toHaveBeenCalled();
    expect(dateInput()).toHaveValue('');

    fireEvent.change(dateInput(), { target: { value: '2027-09-01' } });
    expect(onCommit).toHaveBeenCalledWith('2027-09-01');
  });

  // 2026 is typed as 0002, then 0020, then 0202: every one of them a complete
  // date the browser reports, and every one of them saved before the bounds
  // existed. The last of those was what the field then showed, in year 20.
  it('saves none of the years a year passes through on its way in', () => {
    const { onCommit } = field('');

    fireEvent.focusIn(dateInput());
    ['0002-09-01', '0020-09-01', '0202-09-01'].forEach((partial) =>
      fireEvent.change(dateInput(), { target: { value: partial } })
    );

    expect(onCommit).not.toHaveBeenCalled();

    fireEvent.change(dateInput(), { target: { value: '2026-09-01' } });
    expect(onCommit).toHaveBeenCalledExactlyOnceWith('2026-09-01');
  });

  it('puts the stored day back when what was typed is out of bounds', () => {
    const { onCommit } = field('2026-09-01');

    fireEvent.focusIn(dateInput());
    fireEvent.change(dateInput(), { target: { value: '0020-09-01' } });
    // No value on the blur: leaving a field does not change what is in it, and
    // an override here makes React put the rejected day back after the handler.
    fireEvent.blur(dateInput());

    expect(onCommit).not.toHaveBeenCalled();
    expect(dateInput()).toHaveValue('2026-09-01');
  });

  it('refuses a day further out than the field allows', () => {
    const { onCommit } = field('');

    fireEvent.focusIn(dateInput());
    fireEvent.change(dateInput(), { target: { value: '2099-01-01' } });
    fireEvent.blur(dateInput());

    expect(onCommit).not.toHaveBeenCalled();
  });

  // The state the user was left in: a year saved before there were bounds,
  // which the calendar then opened in the wrong century.
  it('shows a stored day the bounds would refuse as no day at all', () => {
    field('0020-09-01');

    expect(dateInput()).toHaveValue('');
  });

  it('saves an emptied field once the user leaves it', () => {
    const { onCommit } = field('2026-09-01');

    fireEvent.focusIn(dateInput());
    fireEvent.change(dateInput(), { target: { value: '' } });
    fireEvent.blur(dateInput());

    expect(onCommit).toHaveBeenCalledWith('');
  });

  it('leaves the day alone when nothing about it changed', () => {
    const { onCommit } = field('2026-09-01');

    fireEvent.focusIn(dateInput());
    fireEvent.blur(dateInput());

    expect(onCommit).not.toHaveBeenCalled();
  });

  it('does not let a background refresh rewrite a day being typed', () => {
    const { rerender } = field('2026-09-01');

    fireEvent.focusIn(dateInput());
    fireEvent.change(dateInput(), { target: { value: '' } });
    rerender(<DateField id="d" value="2026-09-01" onCommit={vi.fn()} min={MIN} max={MAX} />);

    expect(dateInput()).toHaveValue('');
  });

  it('follows the stored day again once the field is left', () => {
    const { rerender } = field('2026-09-01');

    fireEvent.focusIn(dateInput());
    fireEvent.blur(dateInput());
    rerender(<DateField id="d" value="2026-10-05" onCommit={vi.fn()} min={MIN} max={MAX} />);

    expect(dateInput()).toHaveValue('2026-10-05');
  });

  // On its own button, not on the field: a picker that opens on every click is
  // a field nobody can type a date into.
  it('opens the browser calendar from the button beside the field', () => {
    field('');
    const showPicker = vi.fn();
    (dateInput() as HTMLInputElement & { showPicker: () => void }).showPicker = showPicker;

    fireEvent.click(screen.getByRole('button', { name: /Open calendar/i }));

    expect(showPicker).toHaveBeenCalled();
  });

  it('leaves the field alone when it is clicked itself', () => {
    field('');
    const showPicker = vi.fn();
    (dateInput() as HTMLInputElement & { showPicker: () => void }).showPicker = showPicker;

    fireEvent.click(dateInput());

    expect(showPicker).not.toHaveBeenCalled();
  });

  it('stays usable in a browser that refuses to open one', () => {
    field('');
    (dateInput() as HTMLInputElement & { showPicker: () => void }).showPicker = () => {
      throw new Error('NotAllowedError');
    };

    expect(() =>
      fireEvent.click(screen.getByRole('button', { name: /Open calendar/i }))
    ).not.toThrow();
  });
});
