import os

import pytest

from cloud_asset_audit.config import Account, AwsConfig
from cloud_asset_audit.providers.aws import AwsProvider


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-2")
    os.environ.pop("AWS_PROFILE", None)


@pytest.fixture
def aws_provider():
    config = AwsConfig(regions=("ap-northeast-2",), accounts=(Account("svc-a-dev", "111111111111"),))
    return AwsProvider(config)
