"""GCP clients through Application Default Credentials and service account impersonation."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from cloud_asset_audit.config import GcpConfig

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
CLIENTS = {
    "firewalls": ("google.cloud.compute_v1", "FirewallsClient"),
    "instances": ("google.cloud.compute_v1", "InstancesClient"),
    "machine_types": ("google.cloud.compute_v1", "MachineTypesClient"),
    "disks": ("google.cloud.compute_v1", "DisksClient"),
    "addresses": ("google.cloud.compute_v1", "AddressesClient"),
    "subnetworks": ("google.cloud.compute_v1", "SubnetworksClient"),
    "forwarding_rules": ("google.cloud.compute_v1", "ForwardingRulesClient"),
    "global_forwarding_rules": ("google.cloud.compute_v1", "GlobalForwardingRulesClient"),
    "backend_services": ("google.cloud.compute_v1", "BackendServicesClient"),
    "url_maps": ("google.cloud.compute_v1", "UrlMapsClient"),
    "target_https_proxies": ("google.cloud.compute_v1", "TargetHttpsProxiesClient"),
    "target_http_proxies": ("google.cloud.compute_v1", "TargetHttpProxiesClient"),
    "images": ("google.cloud.compute_v1", "ImagesClient"),
    "projects": ("google.cloud.resourcemanager_v3", "ProjectsClient"),
    "iam_admin": ("google.cloud.iam_admin_v1", "IAMClient"),
    "container": ("google.cloud.container_v1", "ClusterManagerClient"),
}


class GcpProvider:
    cloud = "GCP"

    def __init__(self, config: GcpConfig) -> None:
        self.config = config
        self._credentials: Any = None

    @property
    def projects(self) -> tuple[str, ...]:
        return self.config.projects

    @property
    def credentials(self) -> Any:
        if self._credentials is None:
            import google.auth
            from google.auth import impersonated_credentials

            source, _ = google.auth.default(scopes=SCOPES)
            target = self.config.impersonate_service_account
            self._credentials = (
                impersonated_credentials.Credentials(
                    source_credentials=source, target_principal=target, target_scopes=SCOPES
                )
                if target
                else source
            )
        return self._credentials

    def client(self, name: str) -> Any:
        module, attr = CLIENTS[name]
        return getattr(import_module(module), attr)(credentials=self.credentials)

    def logging_client(self, project: str) -> Any:
        from google.cloud import logging as cloud_logging

        return cloud_logging.Client(project=project, credentials=self.credentials)

    def display_name(self, project: str) -> str:
        return self.client("projects").get_project(name=f"projects/{project}").display_name
