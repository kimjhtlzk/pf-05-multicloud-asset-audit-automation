from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def to_local(value: datetime | str | None, tz: str = "Asia/Seoul") -> str:
    """Format a timestamp in the configured timezone. Unknown values stay empty."""
    if value is None or value in ("", "N/A", "no_information"):
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M:%S")


def previous_month(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Start of last month and start of this month, in UTC."""
    now = now or datetime.now(UTC)
    end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = (end - timedelta(days=1)).replace(day=1)
    return start, end
