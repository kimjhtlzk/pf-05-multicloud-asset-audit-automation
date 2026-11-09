from types import SimpleNamespace as NS
from unittest.mock import MagicMock

from cloud_asset_audit.collectors import firewall, unused, vpc
from cloud_asset_audit.config import Account


def _gcp(clients):
    provider = MagicMock(projects=("example-project",))
    provider.display_name.return_value = "demo"
    provider.client.side_effect = lambda name: clients[name]
    return provider


def test_gcp_firewall_reads_deny_rules():
    rule = NS(
        name="deny-all",
        id=1,
        direction="EGRESS",
        allowed=[],
        denied=[NS(I_p_protocol="all", ports=[])],
        source_ranges=[],
        destination_ranges=["0.0.0.0/0"],
        priority=65534,
        target_tags=[],
        network="global/networks/demo",
        creation_timestamp="2026-01-01T00:00:00Z",
    )
    client = MagicMock()
    client.list.return_value = [rule]
    [row] = firewall.collect_gcp(_gcp({"firewalls": client}))
    assert (row.action, row.priority, row.vpc, row.ports) == ("DENY", "65534", "demo", "all")


def test_gcp_unused_covers_ip_disk_and_orphan_firewall():
    instances = MagicMock()
    instances.aggregated_list.return_value = [("zones/z", NS(instances=[NS(tags=NS(items=["web"]))]))]
    addresses = MagicMock()
    addresses.aggregated_list.return_value = [
        (
            "regions/r",
            NS(
                addresses=[
                    NS(name="ip", address="203.0.113.5", status="RESERVED"),
                    NS(name="used", address="203.0.113.6", status="IN_USE"),
                ]
            ),
        )
    ]
    disks = MagicMock()
    disks.aggregated_list.return_value = [
        (
            "zones/z",
            NS(disks=[NS(name="idle", size_gb=10, users=[]), NS(name="busy", size_gb=10, users=["x"])]),
        )
    ]
    firewalls = MagicMock()
    firewalls.list.return_value = [NS(name="old", target_tags=["gone"]), NS(name="live", target_tags=["web"])]
    rows = unused.collect_gcp(
        _gcp({"instances": instances, "addresses": addresses, "disks": disks, "firewalls": firewalls})
    )
    assert {(r.resource_type, r.resource.split(" ")[0]) for r in rows} == {
        ("IP", "ip"),
        ("DISK", "idle"),
        ("FIREWALL", "old"),
    }


def _tencent(service_clients):
    account = Account("svc-c", "1")
    provider = MagicMock()
    provider.regional.side_effect = lambda service: [
        (account, "ap-seoul", service_clients[service], MagicMock())
    ]
    return provider


def test_tencent_vpc_joins_subnet_to_vpc():
    client = MagicMock()
    client.DescribeVpcs.return_value = NS(VpcSet=[NS(VpcId="v1", VpcName="demo", CidrBlock="10.2.0.0/16")])
    client.DescribeSubnets.return_value = NS(
        SubnetSet=[NS(VpcId="v1", SubnetName="s1", CidrBlock="10.2.1.0/24", Zone="ap-seoul-1")]
    )
    [row] = vpc.collect_tencent(_tencent({"vpc": client}))
    assert (row.vpc_name, row.subnet_cidr, row.az) == ("demo", "10.2.1.0/24", "ap-seoul-1")


def test_tencent_unused_skips_default_group():
    vpc_client = MagicMock()
    vpc_client.DescribeAddresses.return_value = NS(
        AddressSet=[NS(InstanceId=None, AddressName="ip", AddressId="eip-1", AddressIp="203.0.113.7")]
    )
    stat = NS(CVM=0, CDB=0, ENI=0, SG=0, CLB=0)
    vpc_client.DescribeSecurityGroups.return_value = NS(
        SecurityGroupSet=[
            NS(IsDefault=True, SecurityGroupName="default", SecurityGroupId="sg-0"),
            NS(IsDefault=False, SecurityGroupName="idle", SecurityGroupId="sg-1"),
        ]
    )
    vpc_client.DescribeSecurityGroupAssociationStatistics.return_value = NS(
        SecurityGroupAssociationStatisticsSet=[stat]
    )
    cbs = MagicMock()
    cbs.DescribeDisks.return_value = NS(
        DiskSet=[
            NS(DiskState="UNATTACHED", DiskName="d", DiskId="disk-1", DiskSize=10),
            NS(DiskState="ATTACHED", DiskName="b", DiskId="disk-2", DiskSize=10),
        ]
    )
    rows = unused.collect_tencent(_tencent({"vpc": vpc_client, "cbs": cbs}))
    assert sorted(r.resource_type for r in rows) == ["DISK", "IP", "SECURITY_GROUP"]
    assert not any("default" in r.resource for r in rows)
