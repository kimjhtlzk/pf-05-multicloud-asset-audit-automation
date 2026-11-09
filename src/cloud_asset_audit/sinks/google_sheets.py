"""Replace a worksheet and apply the same formatting every run."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cloud_asset_audit.models import Record

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
HEADER_COLOR = {"red": 0.643, "green": 0.761, "blue": 0.957}


def format_requests(sheet_id: int, rows: int, columns: int) -> list[dict[str, Any]]:
    """Header style, filter over the data, automatic column width, frozen header."""
    return [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "endColumnIndex": columns,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": HEADER_COLOR,
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "fontSize": 11,
                            "bold": True,
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": rows,
                        "endColumnIndex": columns,
                    }
                }
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": columns,
                }
            }
        },
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]


def open_spreadsheet(spreadsheet_id: str) -> Any:
    import google.auth
    import gspread

    credentials, _ = google.auth.default(scopes=SCOPES)
    return gspread.authorize(credentials).open_by_key(spreadsheet_id)


def upload(records: Sequence[Record], spreadsheet: Any, worksheet_name: str | None = None) -> int:
    if not records:
        return 0
    header = records[0].headers()
    body = [header, *(record.row() for record in records)]
    worksheet = spreadsheet.worksheet(worksheet_name or records[0].sheet)
    worksheet.clear()
    if worksheet.row_count < len(body):
        worksheet.resize(rows=len(body))
    worksheet.update(body, "A1")
    spreadsheet.batch_update({"requests": format_requests(worksheet.id, len(body), len(header))})
    return len(records)
