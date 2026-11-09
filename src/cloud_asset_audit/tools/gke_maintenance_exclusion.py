"""Keep a rolling exclusion window so a stabilizing service is not auto-upgraded."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

EXCLUSION_NAME = "service stabilization"
WEEKDAY_EVENINGS = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
WINDOW_START = "1970-01-01T18:00:00Z"
WINDOW_END = "1970-01-02T00:00:00Z"


def exclusion_range(now: datetime | None = None) -> tuple[str, str]:
    """From yesterday to 29 days ahead, re-computed on every run."""
    today = (now or datetime.now(UTC)).replace(hour=0, minute=0, second=0, microsecond=0)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (today - timedelta(days=1)).strftime(fmt), (today + timedelta(days=29)).strftime(fmt)


def build_policy(resource_version: str, now: datetime | None = None) -> Any:
    from google.cloud import container_v1

    start, end = exclusion_range(now)
    return container_v1.MaintenancePolicy(
        window=container_v1.MaintenanceWindow(
            recurring_window=container_v1.RecurringTimeWindow(
                window=container_v1.TimeWindow(start_time=WINDOW_START, end_time=WINDOW_END),
                recurrence=WEEKDAY_EVENINGS,
            ),
            maintenance_exclusions={EXCLUSION_NAME: container_v1.TimeWindow(start_time=start, end_time=end)},
        ),
        resource_version=resource_version,
    )


def apply(client: Any, project: str, location: str, cluster: str) -> Any:
    name = f"projects/{project}/locations/{location}/clusters/{cluster}"
    current = client.get_cluster(name=name)
    return client.set_maintenance_policy(
        name=name, maintenance_policy=build_policy(current.maintenance_policy.resource_version)
    )
