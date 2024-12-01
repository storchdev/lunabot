from datetime import datetime 
from zoneinfo import ZoneInfo


def get_unique_day_string() -> str:
    # Define the timezone
    central = ZoneInfo("US/Central")
    # Get the current time in Eastern time
    return datetime.now(central).strftime("%Y-%m-%d")  # Format as YYYYMMDD or any preferred format
