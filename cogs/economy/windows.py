"""Month-based availability windows for limited-time items and gacha banners.

Windows are lists of calendar months evaluated in US Eastern time, so they
recur every year. `None` means always available.
"""

import calendar
from datetime import datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def current_month() -> int:
    return datetime.now(tz=EASTERN).month


def is_open(months: list[int] | None) -> bool:
    return months is None or current_month() in months


def format_months(months: list[int] | None) -> str:
    if months is None:
        return "Permanent"
    names = [calendar.month_abbr[m] for m in months]
    if len(names) == 1:
        return calendar.month_name[months[0]]
    return f"{names[0]}–{names[-1]}"


def window_end(months: list[int] | None) -> datetime | None:
    """When the current window closes (start of the first month after it)."""
    if months is None or not is_open(months):
        return None
    now = datetime.now(tz=EASTERN)
    year, month = now.year, now.month
    while month in months:
        month += 1
        if month == 13:
            year, month = year + 1, 1
        if month == now.month:  # every month is in the window
            return None
    return datetime(year, month, 1, tzinfo=EASTERN)
