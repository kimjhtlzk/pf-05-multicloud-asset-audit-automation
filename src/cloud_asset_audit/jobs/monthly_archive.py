"""Copy audit worksheets to CSV and store them in a year/month folder on Google Drive."""

from __future__ import annotations

import csv
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

FOLDER_MIME = "application/vnd.google-apps.folder"


def archive_period(now: datetime) -> tuple[int, int]:
    """The month being archived is always the previous one."""
    return (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)


def _find_folder(drive: Any, parent: str, name: str) -> str | None:
    query = f"name = '{name}' and '{parent}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
    found = drive.files().list(q=query, fields="files(id)").execute().get("files", [])
    return found[0]["id"] if found else None


def ensure_folder(drive: Any, parent: str, name: str) -> str:
    existing = _find_folder(drive, parent, name)
    if existing:
        return existing
    body = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}
    return drive.files().create(body=body, fields="id").execute()["id"]


def run(
    spreadsheet: Any, drive: Any, parent_folder: str, sheets: tuple[str, ...], now: datetime | None = None
) -> list[str]:
    from googleapiclient.http import MediaFileUpload

    year, month = archive_period(now or datetime.now())
    month_folder = ensure_folder(drive, ensure_folder(drive, parent_folder, str(year)), f"{month:02d}")
    uploaded: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for sheet in sheets:
            path = Path(tmp) / f"{sheet}.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                csv.writer(handle).writerows(spreadsheet.worksheet(sheet).get_all_values())
            media = MediaFileUpload(str(path), mimetype="text/csv")
            drive.files().create(
                body={"name": path.name, "parents": [month_folder]}, media_body=media
            ).execute()
            uploaded.append(path.name)
    return uploaded
