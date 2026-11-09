"""Load settings from YAML. Secrets never live here: they come from environment variables."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Account:
    name: str
    account_id: str = ""
    role: str = ""


@dataclass(frozen=True)
class AwsConfig:
    role_name: str = ""
    regions: tuple[str, ...] = ("ap-northeast-2",)
    accounts: tuple[Account, ...] = ()


@dataclass(frozen=True)
class GcpConfig:
    projects: tuple[str, ...] = ()
    impersonate_service_account: str = ""


@dataclass(frozen=True)
class TencentConfig:
    regions: tuple[str, ...] = ("ap-seoul",)
    accounts: tuple[Account, ...] = ()


@dataclass(frozen=True)
class SheetsConfig:
    spreadsheet_id: str = ""
    archive_folder_id: str = ""
    archive_sheets: tuple[str, ...] = ("AUDIT",)


@dataclass(frozen=True)
class NotifyConfig:
    slack_webhook_env: str = "SLACK_WEBHOOK_URL"
    telegram_token_env: str = "TELEGRAM_BOT_TOKEN"  # noqa: S105 - variable name, not a value
    telegram_chat_id_env: str = "TELEGRAM_CHAT_ID"


@dataclass(frozen=True)
class UnusedConfig:
    exclude_security_group_names: tuple[str, ...] = ("default",)
    exclude_security_group_prefixes: tuple[str, ...] = ("k8s-",)


@dataclass(frozen=True)
class Config:
    timezone: str = "Asia/Seoul"
    aws: AwsConfig = field(default_factory=AwsConfig)
    gcp: GcpConfig = field(default_factory=GcpConfig)
    tencent: TencentConfig = field(default_factory=TencentConfig)
    sheets: SheetsConfig = field(default_factory=SheetsConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    unused: UnusedConfig = field(default_factory=UnusedConfig)


def _accounts(items: list[dict[str, Any]] | None) -> tuple[Account, ...]:
    return tuple(Account(**item) for item in items or [])


def parse(raw: dict[str, Any]) -> Config:
    aws = dict(raw.get("aws") or {})
    tencent = dict(raw.get("tencent") or {})
    gcp = dict(raw.get("gcp") or {})
    sheets = dict(raw.get("sheets") or {})
    unused = dict(raw.get("unused") or {})
    return Config(
        timezone=raw.get("timezone", "Asia/Seoul"),
        aws=AwsConfig(
            role_name=aws.get("role_name", ""),
            regions=tuple(aws.get("regions", ("ap-northeast-2",))),
            accounts=_accounts(aws.get("accounts")),
        ),
        gcp=GcpConfig(
            projects=tuple(gcp.get("projects", ())),
            impersonate_service_account=gcp.get("impersonate_service_account", ""),
        ),
        tencent=TencentConfig(
            regions=tuple(tencent.get("regions", ("ap-seoul",))),
            accounts=_accounts(tencent.get("accounts")),
        ),
        sheets=SheetsConfig(
            spreadsheet_id=sheets.get("spreadsheet_id", ""),
            archive_folder_id=sheets.get("archive_folder_id", ""),
            archive_sheets=tuple(sheets.get("archive_sheets", ("AUDIT",))),
        ),
        notify=NotifyConfig(**(raw.get("notify") or {})),
        unused=UnusedConfig(
            exclude_security_group_names=tuple(unused.get("exclude_security_group_names", ("default",))),
            exclude_security_group_prefixes=tuple(unused.get("exclude_security_group_prefixes", ("k8s-",))),
        ),
    )


def load(path: str | Path) -> Config:
    return parse(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
