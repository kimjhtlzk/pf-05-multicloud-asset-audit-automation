"""Normalize last month's audit events from CloudTrail, Cloud Logging, and CloudAudit."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from cloud_asset_audit.models import AuditEvent
from cloud_asset_audit.rules import is_critical
from cloud_asset_audit.timeutil import previous_month, to_local

AWS_EVENTS = {
    "ACCOUNT": ("CreateUser", "DeleteUser"),
    "POLICY": ("AttachUserPolicy", "DetachUserPolicy"),
    "KEY": ("CreateAccessKey", "DeleteAccessKey"),
    "FIREWALL": (
        "AuthorizeSecurityGroupIngress",
        "AuthorizeSecurityGroupEgress",
        "RevokeSecurityGroupIngress",
        "RevokeSecurityGroupEgress",
    ),
    "INSTANCE": (
        "RunInstances",
        "TerminateInstances",
        "ModifyInstanceAttribute",
        "ModifyVolume",
        "AttachVolume",
        "DetachVolume",
        "StartInstances",
        "StopInstances",
    ),
}
TENCENT_EVENTS = {
    "ACCOUNT": ("AddUser", "DeleteUser"),
    "POLICY": ("AttachUserPolicy", "AttachUserPolicies", "DetachUserPolicy", "DetachUserPolicies"),
    "KEY": ("CreateApiKey", "DeleteApiKey"),
    "FIREWALL": (
        "CreateSecurityGroupPolicies",
        "DeleteSecurityGroupPolicies",
        "ModifySecurityGroupPolicies",
        "ReplaceSecurityGroupPolicies",
    ),
    "INSTANCE": (
        "RunInstances",
        "TerminateInstances",
        "ResetInstancesType",
        "ResizeDisk",
        "StartInstances",
        "StopInstances",
    ),
}
GCP_SYSTEM_ACTORS = (
    'protoPayload.authenticationInfo.principalEmail =~ "^service-"',
    'protoPayload.authenticationInfo.principalEmail =~ "system.gserviceaccount.com"',
    'protoPayload.authenticationInfo.principalEmail =~ "container-engine-robot"',
    'protoPayload.authenticationInfo.principalEmail =~ "^[0-9]"',
)
GCP_QUERIES = {
    "POLICY": (("SetIamPolicy",), True),
    "KEY": (
        ("google.iam.admin.v1.CreateServiceAccountKey", "google.iam.admin.v1.DeleteServiceAccountKey"),
        False,
    ),
    "FIREWALL": (("v1.compute.firewalls.patch", "v1.compute.firewalls.delete"), True),
    "INSTANCE": (
        (
            "v1.compute.instances.insert",
            "v1.compute.instances.delete",
            "v1.compute.instances.setMachineType",
            "v1.compute.disks.resize",
            "v1.compute.instances.attachDisk",
            "v1.compute.instances.detachDisk",
            "v1.compute.instances.start",
            "v1.compute.instances.stop",
        ),
        False,
    ),
}


def _category(action: str, table: dict[str, tuple[str, ...]]) -> str:
    return next((name for name, actions in table.items() if action in actions), "OTHER")


def collect_aws(
    provider: Any, tz: str = "Asia/Seoul", window: tuple[datetime, datetime] | None = None
) -> list[AuditEvent]:
    start, end = window or previous_month()
    records: list[AuditEvent] = []
    for account, region, client in provider.regional("cloudtrail"):
        for page in client.get_paginator("lookup_events").paginate(
            LookupAttributes=[{"AttributeKey": "ReadOnly", "AttributeValue": "false"}],
            StartTime=start,
            EndTime=end,
        ):
            for event in page["Events"]:
                name = event["EventName"]
                category = _category(name, AWS_EVENTS)
                if category == "OTHER":
                    continue
                body = json.loads(event.get("CloudTrailEvent", "{}"))
                records.append(
                    AuditEvent(
                        cloud="AWS",
                        project=account.name,
                        project_id=account.account_id,
                        worker=event.get("Username", ""),
                        action=name,
                        category=category,
                        target=", ".join(r.get("ResourceName", "") for r in event.get("Resources", [])),
                        detail=json.dumps(body.get("requestParameters") or {}, sort_keys=True)[:500],
                        region=region,
                        action_time=to_local(event.get("EventTime"), tz),
                        critical="Y" if is_critical("AWS", name) else "",
                    )
                )
    return records


def gcp_filter(methods: tuple[str, ...], exclude_system: bool, start: datetime, end: datetime) -> str:
    match = " OR ".join(f'protoPayload.methodName="{m}"' for m in methods)
    query = f'({match}) AND timestamp >= "{start.isoformat()}" AND timestamp < "{end.isoformat()}"'
    if exclude_system:
        query += " AND NOT (" + " OR ".join(GCP_SYSTEM_ACTORS) + ")"
    return query


def collect_gcp(
    provider: Any, tz: str = "Asia/Seoul", window: tuple[datetime, datetime] | None = None
) -> list[AuditEvent]:
    start, end = window or previous_month()
    records: list[AuditEvent] = []
    for project in provider.projects:
        display = provider.display_name(project)
        client = provider.logging_client(project)
        for category, (methods, exclude_system) in GCP_QUERIES.items():
            for entry in client.list_entries(filter_=gcp_filter(methods, exclude_system, start, end)):
                payload = entry.payload or {}
                method = payload.get("methodName", "")
                records.append(
                    AuditEvent(
                        cloud="GCP",
                        project=display,
                        project_id=project,
                        worker=payload.get("authenticationInfo", {}).get("principalEmail", ""),
                        action=method,
                        category=category,
                        target=payload.get("resourceName", ""),
                        detail=json.dumps(payload.get("request") or {}, sort_keys=True, default=str)[:500],
                        action_time=to_local(entry.timestamp, tz),
                        critical="Y"
                        if is_critical("GCP", method.rsplit(".", 1)[-1]) or is_critical("GCP", method)
                        else "",
                    )
                )
    return records


def collect_tencent(
    provider: Any, tz: str = "Asia/Seoul", window: tuple[datetime, datetime] | None = None
) -> list[AuditEvent]:
    start, end = window or previous_month()
    records: list[AuditEvent] = []
    for account, region, client, models in provider.regional("cloudaudit"):
        request = models.DescribeEventsRequest()
        request.StartTime = int(start.timestamp())
        request.EndTime = int(end.timestamp())
        request.MaxResults = 50
        while True:
            response = client.DescribeEvents(request)
            for event in response.Events or []:
                name = event.EventName
                category = _category(name, TENCENT_EVENTS)
                if category == "OTHER":
                    continue
                records.append(
                    AuditEvent(
                        cloud="TENCENT",
                        project=account.name,
                        project_id=account.account_id,
                        worker=event.Username or "",
                        action=name,
                        category=category,
                        target=getattr(event.Resources, "ResourceName", "") if event.Resources else "",
                        detail=(event.CloudAuditEvent or "")[:500],
                        region=region,
                        action_time=to_local(event.EventTime, tz) or event.EventTime,
                        critical="Y" if is_critical("TENCENT", name) else "",
                    )
                )
            if response.ListOver:
                break
            request.NextToken = response.NextToken
    return records
