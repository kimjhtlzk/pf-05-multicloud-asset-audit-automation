from __future__ import annotations

from typing import Any

from cloud_asset_audit.models import Vpc


def _tag(item: dict[str, Any]) -> str:
    return next((t["Value"] for t in item.get("Tags", []) if t["Key"] == "Name"), "")


def collect_aws(provider: Any) -> list[Vpc]:
    records: list[Vpc] = []
    for account, region, client in provider.regional("ec2"):
        vpcs = {v["VpcId"]: v for v in client.describe_vpcs()["Vpcs"]}
        for subnet in client.describe_subnets()["Subnets"]:
            vpc = vpcs[subnet["VpcId"]]
            extra = [a["CidrBlock"] for a in vpc.get("CidrBlockAssociationSet", [])][1:]
            records.append(
                Vpc(
                    cloud="AWS",
                    project=account.name,
                    project_id=account.account_id,
                    vpc_name=_tag(vpc) or vpc["VpcId"],
                    vpc_cidr=vpc["CidrBlock"],
                    region=region,
                    subnet_name=_tag(subnet) or subnet["SubnetId"],
                    subnet_cidr=subnet["CidrBlock"],
                    az=subnet["AvailabilityZone"],
                    secondary_ip_cidr=", ".join(extra),
                )
            )
    return records


def collect_gcp(provider: Any) -> list[Vpc]:
    records: list[Vpc] = []
    client = provider.client("subnetworks")
    for project in provider.projects:
        display = provider.display_name(project)
        for scope, listing in client.aggregated_list(project=project):
            for subnet in listing.subnetworks or []:
                records.append(
                    Vpc(
                        cloud="GCP",
                        project=display,
                        project_id=project,
                        vpc_name=subnet.network.rsplit("/", 1)[-1],
                        vpc_cidr="",
                        region=scope.rsplit("/", 1)[-1],
                        subnet_name=subnet.name,
                        subnet_cidr=subnet.ip_cidr_range,
                        secondary_ip_cidr=", ".join(r.ip_cidr_range for r in subnet.secondary_ip_ranges),
                    )
                )
    return records


def collect_tencent(provider: Any) -> list[Vpc]:
    records: list[Vpc] = []
    for account, region, client, models in provider.regional("vpc"):
        vpcs = {v.VpcId: v for v in client.DescribeVpcs(models.DescribeVpcsRequest()).VpcSet}
        for subnet in client.DescribeSubnets(models.DescribeSubnetsRequest()).SubnetSet:
            vpc = vpcs[subnet.VpcId]
            records.append(
                Vpc(
                    cloud="TENCENT",
                    project=account.name,
                    project_id=account.account_id,
                    vpc_name=vpc.VpcName,
                    vpc_cidr=vpc.CidrBlock,
                    region=region,
                    subnet_name=subnet.SubnetName,
                    subnet_cidr=subnet.CidrBlock,
                    az=subnet.Zone,
                )
            )
    return records
