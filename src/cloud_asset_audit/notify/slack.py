from __future__ import annotations

import os

from cloud_asset_audit.notify._http import post_json


def send(text: str, webhook_env: str = "SLACK_WEBHOOK_URL") -> bool:
    url = os.environ.get(webhook_env, "")
    if not url:
        return False
    post_json(url, {"text": text})
    return True
