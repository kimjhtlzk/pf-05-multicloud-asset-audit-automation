"""AWS sessions through the standard credential chain and a cross-account role."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import boto3

from cloud_asset_audit.config import Account, AwsConfig


class AwsProvider:
    cloud = "AWS"

    def __init__(self, config: AwsConfig, base_session: boto3.Session | None = None) -> None:
        self.config = config
        self.base = base_session or boto3.Session()

    @property
    def accounts(self) -> tuple[Account, ...]:
        return self.config.accounts

    def session(self, account: Account, region: str | None = None) -> boto3.Session:
        if not self.config.role_name:
            return boto3.Session(region_name=region)
        arn = f"arn:aws:iam::{account.account_id}:role/{self.config.role_name}"
        creds = self.base.client("sts").assume_role(RoleArn=arn, RoleSessionName="cloud-asset-audit")[
            "Credentials"
        ]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region,
        )

    def regional(self, service: str) -> Iterator[tuple[Account, str, Any]]:
        for account in self.accounts:
            for region in self.config.regions:
                yield account, region, self.session(account, region).client(service)

    def global_clients(self, service: str) -> Iterator[tuple[Account, Any]]:
        for account in self.accounts:
            yield account, self.session(account, self.config.regions[0]).client(service)
