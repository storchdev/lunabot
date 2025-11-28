from datetime import datetime
from zoneinfo import ZoneInfo
from cogs.utils.time_stuff import localnow
from config import DEFAULT_TIMEZONE


def get_unique_day_string() -> str:
    # Define the timezone
    central = ZoneInfo("America/Chicago")
    # Get the current time in Eastern time
    return datetime.now(central).strftime(
        "%Y-%m-%d"
    )  # Format as YYYYMMDD or any preferred format


def is_santas_sleigh() -> bool:
    a = datetime(2025, 12, 22).astimezone(ZoneInfo(DEFAULT_TIMEZONE))
    b = datetime(2025, 12, 27).astimezone(ZoneInfo(DEFAULT_TIMEZONE))
    return a < localnow() < b
