"""Create or delete disk images (GCP) and snapshots (Tencent Cloud)."""

from __future__ import annotations

from typing import Any


def gcp_create_image(provider: Any, project: str, zone: str, disk: str, image_name: str) -> Any:
    from google.cloud import compute_v1

    resource = compute_v1.Image(name=image_name, source_disk=f"projects/{project}/zones/{zone}/disks/{disk}")
    operation = provider.client("images").insert(project=project, image_resource=resource)
    return operation.result()


def gcp_delete_image(provider: Any, project: str, image_name: str) -> Any:
    return provider.client("images").delete(project=project, image=image_name).result()


def tencent_create_snapshot(provider: Any, account: Any, region: str, disk_id: str, name: str) -> str:
    client = provider.client("cbs", account, region)
    request = provider.models("cbs").CreateSnapshotRequest()
    request.DiskId = disk_id
    request.SnapshotName = name
    return client.CreateSnapshot(request).SnapshotId


def tencent_delete_snapshot(provider: Any, account: Any, region: str, snapshot_id: str) -> None:
    client = provider.client("cbs", account, region)
    request = provider.models("cbs").DeleteSnapshotsRequest()
    request.SnapshotIds = [snapshot_id]
    client.DeleteSnapshots(request)
