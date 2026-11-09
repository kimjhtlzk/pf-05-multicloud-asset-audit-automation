"""Alert on critical audit events."""

from __future__ import annotations

from collections.abc import Sequence

from cloud_asset_audit.config import NotifyConfig
from cloud_asset_audit.models import AuditEvent
from cloud_asset_audit.notify import slack, telegram


def format_alert(event: AuditEvent) -> str:
    return (
        f"[CRITICAL] {event.cloud} / {event.project}\n"
        f"{event.action} by {event.worker or 'unknown'}\n"
        f"target: {event.target or '-'}\n"
        f"time: {event.action_time or '-'}"
    )


def critical_only(events: Sequence[AuditEvent]) -> list[AuditEvent]:
    return [event for event in events if event.critical == "Y"]


def dispatch(events: Sequence[AuditEvent], config: NotifyConfig) -> int:
    """Send one message per critical event to every configured channel. Returns the number of events."""
    critical = critical_only(events)
    for event in critical:
        text = format_alert(event)
        slack.send(text, config.slack_webhook_env)
        telegram.send(text, config.telegram_token_env, config.telegram_chat_id_env)
    return len(critical)
