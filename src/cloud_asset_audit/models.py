"""One schema for every cloud. Field order is the column order in sheets and CSV files."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, ClassVar

EMPTY = "-"


def _cell(value: Any) -> Any:
    if value is None or value == "":
        return EMPTY
    if isinstance(value, list | tuple):
        return "\n".join(str(item) for item in value) if value else EMPTY
    return value


@dataclass(frozen=True)
class Record:
    sheet: ClassVar[str] = ""

    @classmethod
    def headers(cls) -> list[str]:
        return [f.name.upper() for f in fields(cls)]

    def row(self) -> list[Any]:
        return [_cell(getattr(self, f.name)) for f in fields(self)]


@dataclass(frozen=True)
class IamRecord(Record):
    sheet: ClassVar[str] = "IAM"
    cloud: str
    project: str
    project_id: str
    user_name: str
    user_id: str
    user_group: str = ""
    permission: str = ""
    user_creation_time: str = ""
    access_key: str = ""
    access_key_creation_time: str = ""
    last_login: str = ""
    password_last_changed: str = ""


@dataclass(frozen=True)
class FirewallRule(Record):
    sheet: ClassVar[str] = "FIREWALL"
    cloud: str
    project: str
    project_id: str
    security_group: str
    security_group_id: str
    direction: str
    action: str
    source: str = ""
    destination: str = ""
    protocol: str = ""
    ports: str = ""
    priority: str = ""
    tags: str = ""
    vpc: str = ""
    creation_time: str = ""


@dataclass(frozen=True)
class Instance(Record):
    sheet: ClassVar[str] = "INSTANCE"
    cloud: str
    project: str
    project_id: str
    instance_name: str
    instance_id: str
    region: str
    az: str = ""
    machine_type: str = ""
    vcpus: str = ""
    ram: str = ""
    boot_disk: str = ""
    disks: str = ""
    private_ip: str = ""
    public_ip: str = ""
    os: str = ""
    state: str = ""
    hostname: str = ""
    cpu_platform: str = ""
    deletion_protection: str = ""
    creation_time: str = ""
    vpc_name: str = ""
    subnet_name: str = ""


@dataclass(frozen=True)
class LoadBalancer(Record):
    sheet: ClassVar[str] = "LOADBALANCER"
    cloud: str
    project: str
    project_id: str
    loadbalancer_name: str
    loadbalancer_id: str
    loadbalancer_type: str = ""
    loadbalancer_domain: str = ""
    vips: str = ""
    vip_isp: str = ""
    region: str = ""
    master_zone: str = ""
    backup_zone: str = ""
    snat: str = ""
    security_groups: str = ""
    sla_type: str = ""
    internet_max_bandwidth_out: str = ""
    network: str = ""
    pass_to_target: str = ""
    listener_protocol: str = ""
    listener: str = ""
    health_check: str = ""
    creation_time: str = ""


@dataclass(frozen=True)
class Vpc(Record):
    sheet: ClassVar[str] = "VPC"
    cloud: str
    project: str
    project_id: str
    vpc_name: str
    vpc_cidr: str
    region: str
    subnet_name: str = ""
    subnet_cidr: str = ""
    az: str = ""
    secondary_ip_cidr: str = ""


@dataclass(frozen=True)
class UnusedResource(Record):
    sheet: ClassVar[str] = "UNUSED"
    cloud: str
    project: str
    project_id: str
    resource_type: str
    resource: str
    region: str = ""
    use_o_x: str = ""


@dataclass(frozen=True)
class AuditEvent(Record):
    sheet: ClassVar[str] = "AUDIT"
    cloud: str
    project: str
    project_id: str
    worker: str
    action: str
    category: str
    target: str = ""
    detail: str = ""
    region: str = ""
    action_time: str = ""
    critical: str = ""
