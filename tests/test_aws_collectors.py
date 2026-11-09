from unittest.mock import MagicMock

import boto3
from moto import mock_aws

from cloud_asset_audit.collectors import firewall, iam, instance, loadbalancer, unused, vpc
from cloud_asset_audit.config import Account, AwsConfig
from cloud_asset_audit.providers.aws import AwsProvider


POLICY = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:ListBucket","Resource":"*"}]}'


@mock_aws
def test_firewall_splits_rules_per_peer(aws_provider):
    ec2 = boto3.client("ec2")
    vpc_id = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    group = ec2.create_security_group(GroupName="web", Description="web", VpcId=vpc_id)["GroupId"]
    ec2.authorize_security_group_ingress(
        GroupId=group,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 443,
                "ToPort": 443,
                "IpRanges": [{"CidrIp": "203.0.113.0/24"}, {"CidrIp": "198.51.100.0/24"}],
            }
        ],
    )
    rows = [
        r
        for r in firewall.collect_aws(aws_provider)
        if r.security_group == "web" and r.direction == "INGRESS"
    ]
    assert {r.source for r in rows} == {"203.0.113.0/24", "198.51.100.0/24"}
    assert all(r.ports == "443" and r.action == "ALLOW" for r in rows)


@mock_aws
def test_iam_merges_direct_and_group_permissions(aws_provider):
    client = boto3.client("iam")
    client.create_user(UserName="alice")
    arn = client.create_policy(PolicyName="p1", PolicyDocument=POLICY)["Policy"]["Arn"]
    client.attach_user_policy(UserName="alice", PolicyArn=arn)
    client.create_group(GroupName="ops")
    group_arn = client.create_policy(PolicyName="p2", PolicyDocument=POLICY)["Policy"]["Arn"]
    client.attach_group_policy(GroupName="ops", PolicyArn=group_arn)
    client.add_user_to_group(GroupName="ops", UserName="alice")
    key = client.create_access_key(UserName="alice")["AccessKey"]["AccessKeyId"]

    [record] = iam.collect_aws(aws_provider)
    assert record.user_group == "ops"
    assert set(record.permission.split("\n")) == {"p1", "p2"}
    assert record.access_key == key


@mock_aws
def test_vpc_rows_are_per_subnet(aws_provider):
    ec2 = boto3.client("ec2")
    vpc_id = ec2.create_vpc(CidrBlock="10.5.0.0/16")["Vpc"]["VpcId"]
    ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.5.1.0/24", AvailabilityZone="ap-northeast-2a")
    rows = [r for r in vpc.collect_aws(aws_provider) if r.vpc_cidr == "10.5.0.0/16"]
    assert [r.subnet_cidr for r in rows] == ["10.5.1.0/24"]


@mock_aws
def test_instance_reads_type_details(aws_provider):
    ec2 = boto3.client("ec2")
    image = ec2.describe_images()["Images"][0]["ImageId"]
    ec2.run_instances(
        ImageId=image,
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.small",
        TagSpecifications=[{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "app-1"}]}],
    )
    [record] = instance.collect_aws(aws_provider)
    assert record.instance_name == "app-1"
    assert record.vcpus == "2"
    assert record.ram == "2GiB"
    assert record.state == "running"


@mock_aws
def test_unused_finds_idle_resources_and_respects_exclusions(aws_provider):
    ec2 = boto3.client("ec2")
    vpc_id = ec2.create_vpc(CidrBlock="10.6.0.0/16")["Vpc"]["VpcId"]
    allocation = ec2.allocate_address(Domain="vpc")["AllocationId"]
    ec2.create_security_group(GroupName="idle", Description="idle", VpcId=vpc_id)
    ec2.create_security_group(GroupName="k8s-node", Description="skip", VpcId=vpc_id)
    volume = ec2.create_volume(AvailabilityZone="ap-northeast-2a", Size=10)["VolumeId"]

    rows = unused.collect_aws(aws_provider)
    by_type = {
        t: [r.resource for r in rows if r.resource_type == t] for t in ("IP", "SECURITY_GROUP", "DISK")
    }
    assert any(allocation in r for r in by_type["IP"])
    assert any(volume in r for r in by_type["DISK"])
    assert any("idle" in r for r in by_type["SECURITY_GROUP"])
    assert not any("k8s-node" in r for r in by_type["SECURITY_GROUP"])


@mock_aws
def test_loadbalancer_includes_listeners(aws_provider):
    ec2 = boto3.client("ec2")
    vpc_id = ec2.create_vpc(CidrBlock="10.7.0.0/16")["Vpc"]["VpcId"]
    subnets = [
        ec2.create_subnet(VpcId=vpc_id, CidrBlock=f"10.7.{i}.0/24", AvailabilityZone=f"ap-northeast-2{z}")[
            "Subnet"
        ]["SubnetId"]
        for i, z in enumerate("ac")
    ]
    elb = boto3.client("elbv2")
    arn = elb.create_load_balancer(Name="web", Subnets=subnets)["LoadBalancers"][0]["LoadBalancerArn"]
    group = elb.create_target_group(Name="tg", Protocol="HTTP", Port=80, VpcId=vpc_id)["TargetGroups"][0][
        "TargetGroupArn"
    ]
    elb.create_listener(
        LoadBalancerArn=arn,
        Protocol="HTTP",
        Port=80,
        DefaultActions=[{"Type": "forward", "TargetGroupArn": group}],
    )
    [record] = loadbalancer.collect_aws(aws_provider)
    assert record.loadbalancer_name == "web"
    assert record.listener == "80"


def test_session_assumes_cross_account_role(monkeypatch):
    base = MagicMock()
    base.client.return_value.assume_role.return_value = {
        "Credentials": {"AccessKeyId": "a", "SecretAccessKey": "b", "SessionToken": "c"}
    }
    provider = AwsProvider(AwsConfig(role_name="audit-readonly"), base_session=base)
    provider.session(Account("svc", "111111111111"), "ap-northeast-2")
    assert base.client.return_value.assume_role.call_args.kwargs["RoleArn"] == (
        "arn:aws:iam::111111111111:role/audit-readonly"
    )
