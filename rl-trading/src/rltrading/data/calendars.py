"""Trading calendars: which days an exchange is open and when each session closes."""

from datetime import date
from functools import lru_cache

import exchange_calendars as xc
import pandas as pd

# exchange_calendars only builds 20 years of sessions by default, which would silently cut off
# older history. Every calendar here is built from this date instead.
CALENDAR_START = date(1990, 1, 2)


@lru_cache(maxsize=16)
def get_calendar(name: str) -> xc.ExchangeCalendar:
    return xc.get_calendar(name, start=CALENDAR_START)


def sessions(name: str, start: date, end: date) -> pd.DatetimeIndex:
    """Session dates (tz-naive midnight labels) between start and end inclusive."""
    cal = get_calendar(name)
    return pd.DatetimeIndex(cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end)))


def session_closes(name: str, session_dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """UTC close time of each session date. Dates that are not sessions raise ValueError."""
    cal = get_calendar(name)
    return pd.DatetimeIndex([cal.session_close(d) for d in session_dates]).tz_convert("UTC")


def is_session(name: str, day: pd.Timestamp) -> bool:
    return bool(get_calendar(name).is_session(day))
