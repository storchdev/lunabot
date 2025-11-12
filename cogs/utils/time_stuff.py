from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import DEFAULT_TIMEZONE

__all__ = ("next_sunday", "next_day")


def next_sunday(tz=None):
    if tz is None:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    now = datetime.now(tz)
    # Calculate days until next Sunday (0 = Monday, 6 = Sunday)
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0:  # If today is Sunday, go to next Sunday
        days_until_sunday = 7
    next_sunday = now + timedelta(days=days_until_sunday)
    next_sunday_midnight = next_sunday.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return next_sunday_midnight


def next_day(tz=None):
    if tz is None:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    now = datetime.now(tz)
    next_day = now + timedelta(days=1)
    next_day_midnight = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
    return next_day_midnight


def localnow():
    return datetime.now(ZoneInfo(DEFAULT_TIMEZONE))
