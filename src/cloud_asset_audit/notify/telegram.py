from __future__ import annotations

import os

from cloud_asset_audit.notify._http import post_json


def send(
    text: str,
    token_env: str = "TELEGRAM_BOT_TOKEN",  # noqa: S107 - variable name, not a value
    chat_id_env: str = "TELEGRAM_CHAT_ID",
) -> bool:
    token, chat_id = os.environ.get(token_env, ""), os.environ.get(chat_id_env, "")
    if not token or not chat_id:
        return False
    post_json(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat_id, "text": text})
    return True
