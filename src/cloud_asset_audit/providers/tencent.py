"""Tencent Cloud clients from environment credentials, with an optional CAM role per account."""

from __future__ import annotations

from collections.abc import Iterator
from importlib import import_module
from typing import Any

from cloud_asset_audit.config import Account, TencentConfig

SERVICES = {
    "cam": ("tencentcloud.cam.v20190116", "cam_client", "CamClient"),
    "cvm": ("tencentcloud.cvm.v20170312", "cvm_client", "CvmClient"),
    "vpc": ("tencentcloud.vpc.v20170312", "vpc_client", "VpcClient"),
    "clb": ("tencentcloud.clb.v20180317", "clb_client", "ClbClient"),
    "cbs": ("tencentcloud.cbs.v20170312", "cbs_client", "CbsClient"),
    "cloudaudit": ("tencentcloud.cloudaudit.v20190319", "cloudaudit_client", "CloudauditClient"),
}


class TencentProvider:
    """Reads TENCENTCLOUD_SECRET_ID and its partner variable through the SDK's own helper."""

    cloud = "TENCENT"

    def __init__(self, config: TencentConfig) -> None:
        self.config = config

    @property
    def accounts(self) -> tuple[Account, ...]:
        return self.config.accounts

    def _credential(self, account: Account) -> Any:
        from tencentcloud.common import credential

        base = credential.EnvironmentVariableCredential().get_credential()
        if not account.role:
            return base
        return credential.STSAssumeRoleCredential(
            base.secretId, base.secretKey, account.role, "cloud-asset-audit"
        )

    def client(self, service: str, account: Account, region: str) -> Any:
        package, module, cls = SERVICES[service]
        return getattr(import_module(f"{package}.{module}"), cls)(self._credential(account), region)

    def models(self, service: str) -> Any:
        return import_module(f"{SERVICES[service][0]}.models")

    def regional(self, service: str) -> Iterator[tuple[Account, str, Any, Any]]:
        for account in self.accounts:
            for region in self.config.regions:
                yield account, region, self.client(service, account, region), self.models(service)
