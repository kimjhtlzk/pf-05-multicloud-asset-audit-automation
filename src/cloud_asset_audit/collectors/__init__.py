"""Registry of resource collectors. Every module exposes collect_aws, collect_gcp, collect_tencent."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from importlib import import_module
from typing import Any

from cloud_asset_audit.models import Record

RESOURCES = ("iam", "firewall", "instance", "loadbalancer", "vpc", "audit_log", "unused")
CLOUDS = ("aws", "gcp", "tencent")


def collect(resource: str, providers: dict[str, Any], clouds: Iterable[str] = CLOUDS) -> list[Record]:
    module = import_module(f"cloud_asset_audit.collectors.{resource}")
    records: list[Record] = []
    for cloud in clouds:
        records.extend(getattr(module, f"collect_{cloud}")(providers[cloud]))
    return records


def filter_projects(records: Sequence[Record], projects: Sequence[str]) -> list[Record]:
    """Keep only named projects. An empty list keeps everything."""
    if not projects:
        return list(records)
    wanted = set(projects)
    return [r for r in records if {getattr(r, "project", ""), getattr(r, "project_id", "")} & wanted]
