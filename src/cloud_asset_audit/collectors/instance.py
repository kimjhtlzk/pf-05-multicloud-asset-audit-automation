from __future__ import annotations

from typing import Any

from cloud_asset_audit.models import Instance
from cloud_asset_audit.timeutil import to_local


def _tag(item: dict[str, Any], key: str = "Name") -> str:
    return next((t["Value"] for t in item.get("Tags", []) if t["Key"] == key), "")


def collect_aws(provider: Any, tz: str = "Asia/Seoul") -> list[Instance]:
    records: list[Instance] = []
    for account, region, client in provider.regional("ec2"):
        vpcs = {v["VpcId"]: _tag(v) or v["VpcId"] for v in client.describe_vpcs()["Vpcs"]}
        subnets = {s["SubnetId"]: _tag(s) or s["SubnetId"] for s in client.describe_subnets()["Subnets"]}
        specs: dict[str, dict[str, Any]] = {}
        for page in client.get_paginator("describe_instances").paginate():
            for reservation in page["Reservations"]:
                for item in reservation["Instances"]:
                    kind = item["InstanceType"]
                    if kind not in specs:
                        specs[kind] = client.describe_instance_types(InstanceTypes=[kind])["InstanceTypes"][0]
                    protected = client.describe_instance_attribute(
                        InstanceId=item["InstanceId"], Attribute="disableApiTermination"
                    )["DisableApiTermination"]["Value"]
                    volume_ids = [
                        m["Ebs"]["VolumeId"] for m in item.get("BlockDeviceMappings", []) if "Ebs" in m
                    ]
                    volumes = client.describe_volumes(VolumeIds=volume_ids)["Volumes"] if volume_ids else []
                    disks = [f"{v['VolumeId']} ({v['Size']}GiB / {v['VolumeType']})" for v in volumes]
                    root = item.get("RootDeviceName", "")
                    boot = next(
                        (
                            f"{v['Size']}GiB / {v['VolumeType']}"
                            for v in volumes
                            if any(a["Device"] == root for a in v.get("Attachments", []))
                        ),
                        "",
                    )
                    records.append(
                        Instance(
                            cloud="AWS",
                            project=account.name,
                            project_id=account.account_id,
                            instance_name=_tag(item),
                            instance_id=item["InstanceId"],
                            region=region,
                            az=item["Placement"]["AvailabilityZone"],
                            machine_type=kind,
                            vcpus=str(specs[kind]["VCpuInfo"]["DefaultVCpus"]),
                            ram=f"{specs[kind]['MemoryInfo']['SizeInMiB'] / 1024:g}GiB",
                            boot_disk=boot,
                            disks="\n".join(disks),
                            private_ip=item.get("PrivateIpAddress", ""),
                            public_ip=item.get("PublicIpAddress", ""),
                            os=item.get("PlatformDetails", ""),
                            state=item["State"]["Name"],
                            hostname=item.get("PrivateDnsName", ""),
                            cpu_platform=item.get("Architecture", ""),
                            deletion_protection=str(protected),
                            creation_time=to_local(item.get("LaunchTime"), tz),
                            vpc_name=vpcs.get(item.get("VpcId", ""), ""),
                            subnet_name=subnets.get(item.get("SubnetId", ""), ""),
                        )
                    )
    return records


def collect_gcp(provider: Any, tz: str = "Asia/Seoul") -> list[Instance]:
    records: list[Instance] = []
    instances = provider.client("instances")
    machine_types = provider.client("machine_types")
    disks_client = provider.client("disks")
    for project in provider.projects:
        display = provider.display_name(project)
        specs: dict[tuple[str, str], Any] = {}
        for scope, listing in instances.aggregated_list(project=project):
            for item in listing.instances or []:
                zone = scope.rsplit("/", 1)[-1]
                kind = item.machine_type.rsplit("/", 1)[-1]
                if (zone, kind) not in specs:
                    specs[(zone, kind)] = machine_types.get(project=project, zone=zone, machine_type=kind)
                spec = specs[(zone, kind)]
                sizes = []
                boot = ""
                for disk in item.disks:
                    info = disks_client.get(project=project, zone=zone, disk=disk.source.rsplit("/", 1)[-1])
                    label = f"{info.name} ({info.size_gb}GiB / {info.type_.rsplit('/', 1)[-1]})"
                    sizes.append(label)
                    if disk.boot:
                        boot = label
                nic = item.network_interfaces[0]
                public = nic.access_configs[0].nat_i_p if nic.access_configs else ""
                records.append(
                    Instance(
                        cloud="GCP",
                        project=display,
                        project_id=project,
                        instance_name=item.name,
                        instance_id=str(item.id),
                        region=zone.rsplit("-", 1)[0],
                        az=zone,
                        machine_type=kind,
                        vcpus=str(spec.guest_cpus),
                        ram=f"{spec.memory_mb / 1024:g}GiB",
                        boot_disk=boot,
                        disks="\n".join(sizes),
                        private_ip=nic.network_i_p,
                        public_ip=public,
                        state=item.status,
                        hostname=item.hostname,
                        cpu_platform=item.cpu_platform,
                        deletion_protection=str(item.deletion_protection),
                        creation_time=to_local(item.creation_timestamp, tz),
                        vpc_name=nic.network.rsplit("/", 1)[-1],
                        subnet_name=nic.subnetwork.rsplit("/", 1)[-1],
                    )
                )
    return records


def collect_tencent(provider: Any) -> list[Instance]:
    records: list[Instance] = []
    for account, region, client, models in provider.regional("cvm"):
        request = models.DescribeInstancesRequest()
        request.Limit = 100
        for item in client.DescribeInstances(request).InstanceSet or []:
            data = item.DataDisks or []
            records.append(
                Instance(
                    cloud="TENCENT",
                    project=account.name,
                    project_id=account.account_id,
                    instance_name=item.InstanceName,
                    instance_id=item.InstanceId,
                    region=region,
                    az=item.Placement.Zone,
                    machine_type=item.InstanceType,
                    vcpus=str(item.CPU),
                    ram=f"{item.Memory}GiB",
                    boot_disk=f"{item.SystemDisk.DiskSize}GiB / {item.SystemDisk.DiskType}",
                    disks="\n".join(f"{d.DiskId} ({d.DiskSize}GiB / {d.DiskType})" for d in data),
                    private_ip=", ".join(item.PrivateIpAddresses or []),
                    public_ip=", ".join(item.PublicIpAddresses or []),
                    os=item.OsName,
                    state=item.InstanceState,
                    creation_time=item.CreatedTime,
                    vpc_name=item.VirtualPrivateCloud.VpcId,
                    subnet_name=item.VirtualPrivateCloud.SubnetId,
                )
            )
    return records
