from datetime import datetime, timedelta 
from zoneinfo import ZoneInfo
from discord.utils import sleep_until

__all__ = (
    'sleep_until_next_sunday',
)

async def sleep_until_next_sunday(tz=None):
    if tz is None:
        tz = ZoneInfo("America/Chicago")
    now = datetime.now(tz)
    # Calculate days until next Sunday (0 = Monday, 6 = Sunday)
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0:  # If today is Sunday, go to next Sunday
        days_until_sunday = 7
    next_sunday = now + timedelta(days=days_until_sunday)
    next_sunday_midnight = next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)
    await sleep_until(next_sunday_midnight)
