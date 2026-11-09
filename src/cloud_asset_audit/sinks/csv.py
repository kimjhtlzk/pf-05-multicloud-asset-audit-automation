from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from cloud_asset_audit.models import Record


def write(records: Sequence[Record], directory: str | Path, name: str | None = None) -> Path | None:
    """Write one CSV. UTF-8 with BOM so spreadsheet tools read Korean text correctly."""
    if not records:
        return None
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{(name or records[0].sheet).lower()}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(records[0].headers())
        writer.writerows(record.row() for record in records)
    return path
