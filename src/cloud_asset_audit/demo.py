"""Fake data for the whole pipeline. Needs no credentials and makes no network calls."""

from __future__ import annotations

from cloud_asset_audit.models import (
    AuditEvent,
    FirewallRule,
    IamRecord,
    Instance,
    LoadBalancer,
    Record,
    UnusedResource,
    Vpc,
)
from cloud_asset_audit.rules import is_critical

ACCOUNTS = {
    "AWS": ("svc-a-dev", "111111111111"),
    "GCP": ("svc-b-prd", "example-project-b"),
    "TENCENT": ("svc-c-prd", "111111111111"),
}


def _base(cloud: str) -> dict[str, str]:
    project, project_id = ACCOUNTS[cloud]
    return {"cloud": cloud, "project": project, "project_id": project_id}


def _event(cloud: str, worker: str, action: str, category: str, target: str) -> AuditEvent:
    return AuditEvent(
        **_base(cloud),
        worker=worker,
        action=action,
        category=category,
        target=target,
        action_time="2026-01-15 09:30:00",
        critical="Y" if is_critical(cloud, action) else "",
    )


def records() -> dict[str, list[Record]]:
    return {
        "iam": [
            IamRecord(
                **_base("AWS"),
                user_name="example-admin",
                user_id="AIDAEXAMPLE0001",
                permission="ReadOnlyAccess",
            ),
            IamRecord(
                **_base("GCP"),
                user_name="example-sa",
                user_id="100000000000000000001",
                user_group="serviceAccount",
                permission="roles/viewer",
            ),
            IamRecord(
                **_base("TENCENT"),
                user_name="example-ops",
                user_id="example-uin-1",
                permission="QcloudCVMReadOnlyAccess",
            ),
        ],
        "firewall": [
            FirewallRule(
                **_base("AWS"),
                security_group="web",
                security_group_id="sg-0000000001",
                direction="INGRESS",
                action="ALLOW",
                source="203.0.113.10/32",
                protocol="tcp",
                ports="443",
            ),
            FirewallRule(
                **_base("GCP"),
                security_group="deny-egress",
                security_group_id="1001",
                direction="EGRESS",
                action="DENY",
                destination="0.0.0.0/0",
                protocol="all",
                ports="all",
                priority="65534",
            ),
            FirewallRule(
                **_base("TENCENT"),
                security_group="vpn-only",
                security_group_id="sg-tc000001",
                direction="INGRESS",
                action="ACCEPT",
                source="198.51.100.0/24",
                protocol="TCP",
                ports="22",
            ),
        ],
        "instance": [
            Instance(
                **_base("AWS"),
                instance_name="app-1",
                instance_id="i-0000000001",
                region="ap-northeast-2",
                machine_type="m7i.large",
                vcpus="2",
                ram="8GiB",
                private_ip="10.0.1.10",
                state="running",
            ),
            Instance(
                **_base("GCP"),
                instance_name="app-2",
                instance_id="2001",
                region="asia-northeast3",
                machine_type="n2-standard-4",
                vcpus="4",
                ram="16GiB",
                private_ip="10.1.1.10",
                state="RUNNING",
            ),
            Instance(
                **_base("TENCENT"),
                instance_name="app-3",
                instance_id="ins-000001",
                region="ap-seoul",
                machine_type="S5.LARGE8",
                vcpus="4",
                ram="8GiB",
                private_ip="10.2.1.10",
                state="RUNNING",
            ),
        ],
        "loadbalancer": [
            LoadBalancer(
                **_base("AWS"),
                loadbalancer_name="web-alb",
                loadbalancer_id="0000000001",
                loadbalancer_type="application / internet-facing",
                loadbalancer_domain="web-alb.example.com",
                region="ap-northeast-2",
                listener_protocol="HTTPS",
                listener="443",
            ),
        ],
        "vpc": [
            Vpc(
                **_base("AWS"),
                vpc_name="demo-vpc",
                vpc_cidr="10.0.0.0/16",
                region="ap-northeast-2",
                subnet_name="demo-a",
                subnet_cidr="10.0.1.0/24",
                az="ap-northeast-2a",
            ),
            Vpc(
                **_base("TENCENT"),
                vpc_name="demo-vpc",
                vpc_cidr="10.2.0.0/16",
                region="ap-seoul",
                subnet_name="demo-1",
                subnet_cidr="10.2.1.0/24",
                az="ap-seoul-1",
            ),
        ],
        "audit_log": [
            _event("AWS", "example-admin", "CreateAccessKey", "KEY", "example-user"),
            _event("AWS", "example-admin", "AuthorizeSecurityGroupIngress", "FIREWALL", "sg-0000000001"),
            _event("GCP", "user@example.com", "SetIamPolicy", "POLICY", "projects/example-project-b"),
            _event("TENCENT", "example-ops", "TerminateInstances", "INSTANCE", "ins-000001"),
            _event("TENCENT", "example-ops", "StartInstances", "INSTANCE", "ins-000002"),
        ],
        "unused": [
            UnusedResource(
                **_base("AWS"),
                resource_type="IP",
                resource="(eipalloc-0000000001 / 203.0.113.20)",
                region="ap-northeast-2",
            ),
            UnusedResource(
                **_base("AWS"),
                resource_type="DISK",
                resource="(vol-0000000001 / 100GiB / gp3)",
                region="ap-northeast-2",
            ),
            UnusedResource(
                **_base("GCP"), resource_type="FIREWALL", resource="old-allow-rule", region="global"
            ),
        ],
    }
