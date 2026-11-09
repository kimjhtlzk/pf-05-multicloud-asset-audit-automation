"""Find resources that keep billing while nothing uses them."""

from __future__ import annotations

from typing import Any

from cloud_asset_audit.config import UnusedConfig
from cloud_asset_audit.models import UnusedResource


def _name(item: dict[str, Any]) -> str:
    return next((t["Value"] for t in item.get("Tags", []) if t["Key"].lower() == "name"), "")


def _excluded(name: str, rules: UnusedConfig) -> bool:
    return name in rules.exclude_security_group_names or name.startswith(
        rules.exclude_security_group_prefixes
    )


def collect_aws(provider: Any, rules: UnusedConfig | None = None) -> list[UnusedResource]:
    rules = rules or UnusedConfig()
    records: list[UnusedResource] = []
    for account, region, client in provider.regional("ec2"):
        base = {"cloud": "AWS", "project": account.name, "project_id": account.account_id, "region": region}
        for address in client.describe_addresses()["Addresses"]:
            if not address.get("InstanceId") and not address.get("AssociationId"):
                label = (
                    f"{_name(address)} ({address.get('AllocationId')} / {address.get('PublicIp')})".strip()
                )
                records.append(UnusedResource(resource_type="IP", resource=label, **base))
        for group in client.describe_security_groups()["SecurityGroups"]:
            if _excluded(group["GroupName"], rules):
                continue
            used = client.describe_network_interfaces(
                Filters=[{"Name": "group-id", "Values": [group["GroupId"]]}]
            )["NetworkInterfaces"]
            if not used:
                records.append(
                    UnusedResource(
                        resource_type="SECURITY_GROUP",
                        resource=f"{group['GroupName']} ({group['GroupId']})",
                        **base,
                    )
                )
        for volume in client.describe_volumes()["Volumes"]:
            if not volume["Attachments"]:
                label = (
                    f"{_name(volume)} ({volume['VolumeId']} / {volume['Size']}GiB / {volume['VolumeType']})"
                )
                records.append(UnusedResource(resource_type="DISK", resource=label.strip(), **base))
    return records


def collect_gcp(provider: Any) -> list[UnusedResource]:
    records: list[UnusedResource] = []
    addresses = provider.client("addresses")
    disks = provider.client("disks")
    instances = provider.client("instances")
    firewalls = provider.client("firewalls")
    for project in provider.projects:
        base = {"cloud": "GCP", "project": provider.display_name(project), "project_id": project}
        active_tags = {
            tag
            for _, listing in instances.aggregated_list(project=project)
            for item in listing.instances or []
            for tag in item.tags.items
        }
        for scope, listing in addresses.aggregated_list(project=project):
            for address in listing.addresses or []:
                if address.status == "RESERVED":
                    records.append(
                        UnusedResource(
                            resource_type="IP",
                            resource=f"{address.name} ({address.address})",
                            region=scope.rsplit("/", 1)[-1],
                            **base,
                        )
                    )
        for scope, listing in disks.aggregated_list(project=project):
            for disk in listing.disks or []:
                if not disk.users:
                    records.append(
                        UnusedResource(
                            resource_type="DISK",
                            resource=f"{disk.name} ({disk.size_gb}GiB)",
                            region=scope.rsplit("/", 1)[-1],
                            **base,
                        )
                    )
        for rule in firewalls.list(project=project):
            if rule.target_tags and not set(rule.target_tags) & active_tags:
                records.append(
                    UnusedResource(resource_type="FIREWALL", resource=rule.name, region="global", **base)
                )
    return records


def collect_tencent(provider: Any) -> list[UnusedResource]:
    records: list[UnusedResource] = []
    for account, region, client, models in provider.regional("vpc"):
        base = {
            "cloud": "TENCENT",
            "project": account.name,
            "project_id": account.account_id,
            "region": region,
        }
        for address in client.DescribeAddresses(models.DescribeAddressesRequest()).AddressSet or []:
            if not address.InstanceId:
                records.append(
                    UnusedResource(
                        resource_type="IP",
                        resource=f"{address.AddressName} ({address.AddressId} / {address.AddressIp})",
                        **base,
                    )
                )
        for group in (
            client.DescribeSecurityGroups(models.DescribeSecurityGroupsRequest()).SecurityGroupSet or []
        ):
            if group.IsDefault:
                continue
            request = models.DescribeSecurityGroupAssociationStatisticsRequest()
            request.SecurityGroupIds = [group.SecurityGroupId]
            stats = client.DescribeSecurityGroupAssociationStatistics(
                request
            ).SecurityGroupAssociationStatisticsSet
            if stats and not (stats[0].CVM or stats[0].CDB or stats[0].ENI or stats[0].SG or stats[0].CLB):
                records.append(
                    UnusedResource(
                        resource_type="SECURITY_GROUP",
                        resource=f"{group.SecurityGroupName} ({group.SecurityGroupId})",
                        **base,
                    )
                )
    for account, region, client, models in provider.regional("cbs"):
        base = {
            "cloud": "TENCENT",
            "project": account.name,
            "project_id": account.account_id,
            "region": region,
        }
        for disk in client.DescribeDisks(models.DescribeDisksRequest()).DiskSet or []:
            if disk.DiskState == "UNATTACHED":
                records.append(
                    UnusedResource(
                        resource_type="DISK",
                        resource=f"{disk.DiskName} ({disk.DiskId} / {disk.DiskSize}GiB)",
                        **base,
                    )
                )
    return records
