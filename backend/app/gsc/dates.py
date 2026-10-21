import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bounds() -> tuple[date, date]:
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    month = today.year * 12 + today.month - 1 - 16
    year, zero_month = divmod(month, 12)
    first = date(year, zero_month + 1, min(today.day, calendar.monthrange(year, zero_month + 1)[1]))
    return first, today - timedelta(days=3)


def days_between(start: date, end: date):
    for i in range((end - start).days + 1):
        yield start + timedelta(days=i)
