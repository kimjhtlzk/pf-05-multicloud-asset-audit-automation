import json
from datetime import UTC, datetime
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

from cloud_asset_audit.collectors import audit_log
from cloud_asset_audit.config import Account

WINDOW = (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC))


def _trail(*events):
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = [{"Events": list(events)}]
    provider = MagicMock()
    provider.regional.return_value = [(Account("svc-a-dev", "111111111111"), "ap-northeast-2", client)]
    return provider


def test_aws_keeps_only_tracked_events_and_flags_critical():
    provider = _trail(
        {
            "EventName": "CreateAccessKey",
            "Username": "alice",
            "EventTime": WINDOW[0],
            "CloudTrailEvent": json.dumps({}),
        },
        {
            "EventName": "RunInstances",
            "Username": "bob",
            "EventTime": WINDOW[0],
            "CloudTrailEvent": json.dumps({}),
        },
        {
            "EventName": "ListBuckets",
            "Username": "bob",
            "EventTime": WINDOW[0],
            "CloudTrailEvent": json.dumps({}),
        },
    )
    rows = {r.action: r for r in audit_log.collect_aws(provider, window=WINDOW)}
    assert set(rows) == {"CreateAccessKey", "RunInstances"}
    assert rows["CreateAccessKey"].critical == "Y"
    assert rows["CreateAccessKey"].category == "KEY"
    assert rows["RunInstances"].critical == ""


def test_gcp_filter_excludes_system_actors_only_when_asked():
    with_system = audit_log.gcp_filter(("SetIamPolicy",), True, *WINDOW)
    without = audit_log.gcp_filter(("v1.compute.instances.stop",), False, *WINDOW)
    assert "container-engine-robot" in with_system
    assert "container-engine-robot" not in without
    assert 'methodName="v1.compute.instances.stop"' in without


def test_gcp_flags_short_and_full_method_names():
    entry = NS(
        payload={
            "methodName": "v1.compute.instances.stop",
            "authenticationInfo": {"principalEmail": "a@example.com"},
        },
        timestamp=WINDOW[0],
    )
    logging_client = MagicMock()
    logging_client.list_entries.side_effect = lambda filter_: [entry] if "instances.stop" in filter_ else []
    provider = MagicMock(projects=("example-project",))
    provider.display_name.return_value = "demo"
    provider.logging_client.return_value = logging_client
    [row] = audit_log.collect_gcp(provider, window=WINDOW)
    assert row.critical == "Y"
    assert row.category == "INSTANCE"


def test_tencent_follows_pagination():
    event = NS(
        EventName="CreateApiKey", Username="ops", Resources=None, CloudAuditEvent="{}", EventTime="1767225600"
    )
    client = MagicMock()
    client.DescribeEvents.side_effect = [
        NS(Events=[event], ListOver=False, NextToken="1"),
        NS(Events=[event], ListOver=True, NextToken=None),
    ]
    models = MagicMock()
    provider = MagicMock()
    provider.regional.return_value = [(Account("svc", "1"), "ap-seoul", client, models)]
    rows = audit_log.collect_tencent(provider, window=WINDOW)
    assert len(rows) == 2
    assert all(r.critical == "Y" for r in rows)
