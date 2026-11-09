from __future__ import annotations

from typing import Any

from cloud_asset_audit.models import FirewallRule
from cloud_asset_audit.timeutil import to_local


def _name_tag(tags: list[dict[str, str]] | None) -> str:
    return ", ".join(f"{t['Key']}={t['Value']}" for t in tags or [])


def _aws_ports(rule: dict[str, Any]) -> str:
    if rule.get("IpProtocol") == "-1":
        return "all"
    start, end = rule.get("FromPort"), rule.get("ToPort")
    return str(start) if start == end else f"{start}-{end}"


def collect_aws(provider: Any) -> list[FirewallRule]:
    records: list[FirewallRule] = []
    for account, _region, client in provider.regional("ec2"):
        for page in client.get_paginator("describe_security_groups").paginate():
            for group in page["SecurityGroups"]:
                for direction, key in (("INGRESS", "IpPermissions"), ("EGRESS", "IpPermissionsEgress")):
                    for rule in group.get(key, []):
                        peers = [r["CidrIp"] for r in rule.get("IpRanges", [])]
                        peers += [r["CidrIpv6"] for r in rule.get("Ipv6Ranges", [])]
                        peers += [r["GroupId"] for r in rule.get("UserIdGroupPairs", [])]
                        for peer in peers or [""]:
                            records.append(
                                FirewallRule(
                                    cloud="AWS",
                                    project=account.name,
                                    project_id=account.account_id,
                                    security_group=group["GroupName"],
                                    security_group_id=group["GroupId"],
                                    direction=direction,
                                    action="ALLOW",
                                    source=peer if direction == "INGRESS" else "",
                                    destination=peer if direction == "EGRESS" else "",
                                    protocol=rule.get("IpProtocol", ""),
                                    ports=_aws_ports(rule),
                                    tags=_name_tag(group.get("Tags")),
                                    vpc=group.get("VpcId", ""),
                                )
                            )
    return records


def _gcp_ports(items: Any) -> tuple[str, str]:
    protocols = [i.I_p_protocol for i in items]
    ports = [p for i in items for p in (i.ports or ["all"])]
    return ", ".join(protocols), ", ".join(ports)


def collect_gcp(provider: Any, tz: str = "Asia/Seoul") -> list[FirewallRule]:
    records: list[FirewallRule] = []
    client = provider.client("firewalls")
    for project in provider.projects:
        display = provider.display_name(project)
        for rule in client.list(project=project):
            action = "ALLOW" if rule.allowed else "DENY"
            protocol, ports = _gcp_ports(rule.allowed or rule.denied)
            records.append(
                FirewallRule(
                    cloud="GCP",
                    project=display,
                    project_id=project,
                    security_group=rule.name,
                    security_group_id=str(rule.id),
                    direction=rule.direction,
                    action=action,
                    source=", ".join(rule.source_ranges),
                    destination=", ".join(rule.destination_ranges),
                    protocol=protocol,
                    ports=ports,
                    priority=str(rule.priority),
                    tags=", ".join(rule.target_tags),
                    vpc=rule.network.rsplit("/", 1)[-1],
                    creation_time=to_local(rule.creation_timestamp, tz),
                )
            )
    return records


def collect_tencent(provider: Any) -> list[FirewallRule]:
    records: list[FirewallRule] = []
    for account, _region, client, models in provider.regional("vpc"):
        for group in client.DescribeSecurityGroups(models.DescribeSecurityGroupsRequest()).SecurityGroupSet:
            request = models.DescribeSecurityGroupPoliciesRequest()
            request.SecurityGroupId = group.SecurityGroupId
            policies = client.DescribeSecurityGroupPolicies(request).SecurityGroupPolicySet
            for direction, rules in (("INGRESS", policies.Ingress), ("EGRESS", policies.Egress)):
                for rule in rules or []:
                    records.append(
                        FirewallRule(
                            cloud="TENCENT",
                            project=account.name,
                            project_id=account.account_id,
                            security_group=group.SecurityGroupName,
                            security_group_id=group.SecurityGroupId,
                            direction=direction,
                            action=rule.Action,
                            source=rule.CidrBlock if direction == "INGRESS" else "",
                            destination=rule.CidrBlock if direction == "EGRESS" else "",
                            protocol=rule.Protocol,
                            ports=rule.Port,
                            priority=str(rule.PolicyIndex),
                            creation_time=group.CreatedTime,
                        )
                    )
    return records
