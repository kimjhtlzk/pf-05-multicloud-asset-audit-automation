from __future__ import annotations

from typing import Any

from cloud_asset_audit.models import LoadBalancer
from cloud_asset_audit.timeutil import to_local


def collect_aws(provider: Any, tz: str = "Asia/Seoul") -> list[LoadBalancer]:
    records: list[LoadBalancer] = []
    for account, region, client in provider.regional("elbv2"):
        for page in client.get_paginator("describe_load_balancers").paginate():
            for lb in page["LoadBalancers"]:
                arn = lb["LoadBalancerArn"]
                listeners = client.describe_listeners(LoadBalancerArn=arn)["Listeners"]
                groups = client.describe_target_groups(LoadBalancerArn=arn)["TargetGroups"]
                zones = [z["ZoneName"] for z in lb.get("AvailabilityZones", [])]
                checks = [
                    f"{g['TargetGroupName']}: {g.get('HealthCheckProtocol')}:{g.get('HealthCheckPort')}"
                    for g in groups
                ]
                records.append(
                    LoadBalancer(
                        cloud="AWS",
                        project=account.name,
                        project_id=account.account_id,
                        loadbalancer_name=lb["LoadBalancerName"],
                        loadbalancer_id=arn.rsplit("/", 1)[-1],
                        loadbalancer_type=f"{lb.get('Type', '')} / {lb.get('Scheme', '')}",
                        loadbalancer_domain=lb.get("DNSName", ""),
                        region=region,
                        master_zone=", ".join(zones),
                        security_groups=", ".join(lb.get("SecurityGroups", [])),
                        network=lb.get("VpcId", ""),
                        pass_to_target="\n".join(g["TargetGroupName"] for g in groups),
                        listener_protocol="\n".join(x["Protocol"] for x in listeners),
                        listener="\n".join(str(x["Port"]) for x in listeners),
                        health_check="\n".join(checks),
                        creation_time=to_local(lb.get("CreatedTime"), tz),
                    )
                )
    return records


def _last(url: str) -> str:
    return url.rsplit("/", 1)[-1] if url else ""


def _gcp_backends(provider: Any, project: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Index backend services and the URL map behind each target proxy."""
    backends = {
        b.name: b
        for _, listing in provider.client("backend_services").aggregated_list(project=project)
        for b in listing.backend_services or []
    }
    url_maps = {
        u.name: u
        for _, listing in provider.client("url_maps").aggregated_list(project=project)
        for u in listing.url_maps or []
    }
    proxies: dict[str, str] = {}
    for name in ("target_http_proxies", "target_https_proxies"):
        for _, listing in provider.client(name).aggregated_list(project=project):
            for proxy in getattr(listing, name, None) or []:
                url_map = url_maps.get(_last(proxy.url_map))
                proxies[proxy.name] = _last(url_map.default_service) if url_map else ""
    return backends, proxies


def collect_gcp(provider: Any, tz: str = "Asia/Seoul") -> list[LoadBalancer]:
    records: list[LoadBalancer] = []
    rules_client = provider.client("forwarding_rules")
    for project in provider.projects:
        display = provider.display_name(project)
        backends, proxies = _gcp_backends(provider, project)
        for scope, listing in rules_client.aggregated_list(project=project):
            for rule in listing.forwarding_rules or []:
                name = _last(rule.backend_service) or proxies.get(_last(rule.target), "")
                backend = backends.get(name)
                checks = [_last(h) for h in backend.health_checks] if backend else []
                targets = [_last(b.group) for b in backend.backends] if backend else []
                records.append(
                    LoadBalancer(
                        cloud="GCP",
                        project=display,
                        project_id=project,
                        loadbalancer_name=rule.name,
                        loadbalancer_id=str(rule.id),
                        loadbalancer_type=rule.load_balancing_scheme,
                        vips=rule.I_p_address,
                        region=_last(scope),
                        network=_last(rule.network),
                        pass_to_target="\n".join(targets) or name,
                        listener_protocol=rule.I_p_protocol,
                        listener=rule.port_range or ", ".join(rule.ports),
                        health_check="\n".join(checks),
                        creation_time=to_local(rule.creation_timestamp, tz),
                    )
                )
    return records


def collect_tencent(provider: Any) -> list[LoadBalancer]:
    records: list[LoadBalancer] = []
    for account, region, client, models in provider.regional("clb"):
        for lb in client.DescribeLoadBalancers(models.DescribeLoadBalancersRequest()).LoadBalancerSet or []:
            request = models.DescribeListenersRequest()
            request.LoadBalancerId = lb.LoadBalancerId
            listeners = client.DescribeListeners(request).Listeners or []
            records.append(
                LoadBalancer(
                    cloud="TENCENT",
                    project=account.name,
                    project_id=account.account_id,
                    loadbalancer_name=lb.LoadBalancerName,
                    loadbalancer_id=lb.LoadBalancerId,
                    loadbalancer_type=lb.Forward and "L7" or "L4",
                    loadbalancer_domain=getattr(lb, "LoadBalancerDomain", "") or "",
                    vips=", ".join(lb.LoadBalancerVips or []),
                    vip_isp=getattr(lb, "VipIsp", "") or "",
                    region=region,
                    master_zone=getattr(getattr(lb, "MasterZone", None), "Zone", "") or "",
                    snat=str(getattr(lb, "Snat", "")),
                    security_groups=", ".join(getattr(lb, "SecureGroups", None) or []),
                    sla_type=getattr(lb, "SlaType", "") or "",
                    network=getattr(lb, "VpcId", "") or "",
                    listener_protocol="\n".join(x.Protocol for x in listeners),
                    listener="\n".join(str(x.Port) for x in listeners),
                    creation_time=getattr(lb, "CreateTime", "") or "",
                )
            )
    return records
