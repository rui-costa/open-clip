"""When a run of clips goes out: one slot per clip, spread over days.

Two things publish a project on a schedule — the Postiz import and the YouTube
upload — and they have to agree about what "two a day between nine and nine"
means. The same project spread two different ways is two different calendars
for one set of clips, so the arithmetic lives here once and each caller brings
its own settings, its own start and its own timezone.

Nothing here reads settings or knows about a platform. It is a function of the
clip's own position, which is what makes a slot stable: re-importing or
re-publishing one clip puts it back where it already was, whatever order things
happened in.
"""

from datetime import datetime, timedelta
from typing import Tuple


def day_window(first_hour: int, last_hour: int) -> Tuple[int, int]:
    """The hours a day's slots are spread between, as (first, last).

    Clamped to a real hour, and a window that ends before it begins collapses
    to a single moment rather than running backwards.
    """
    first = min(23, max(0, int(first_hour)))
    last = min(23, max(0, int(last_hour)))
    return (first, last) if last >= first else (first, first)


def slot_time(
    start: datetime,
    index: int,
    per_day: int,
    first_hour: int,
    last_hour: int,
) -> datetime:
    """When the clip at `index` goes out, given a schedule that begins at `start`.

    `per_day` of 0 or less is everything at `start` — one moment for the whole
    project, which is what "all in one go" means and what a publisher did
    before anyone could say otherwise.

    Otherwise the clips fill each day's window evenly, first to last hour, and
    spill onto the following days. Whether the run begins today or tomorrow is
    decided once, from `start`, rather than per clip: deciding it per clip
    moved only the clips whose own slot had already passed, which landed them
    on the day the next clip already had — an afternoon run of three clips at
    one a day produced tomorrow, tomorrow, the day after.

    The timezone is the caller's: `start` is returned or built on, so a UTC
    `start` gives UTC slots and a local one gives local slots.
    """
    if per_day <= 0:
        return start

    day, slot = divmod(max(0, int(index)), per_day)
    first, last = day_window(first_hour, last_hour)
    if per_day == 1:
        hour_of_day = float(first)
    else:
        hour_of_day = first + (last - first) * (slot / (per_day - 1))

    midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
    if midnight + timedelta(hours=first) < start:
        midnight += timedelta(days=1)
    return midnight + timedelta(days=day, hours=hour_of_day)
