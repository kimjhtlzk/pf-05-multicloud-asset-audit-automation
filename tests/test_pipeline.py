import csv
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from cloud_asset_audit import cli, collectors, demo
from cloud_asset_audit.config import NotifyConfig, parse
from cloud_asset_audit.jobs import monthly_archive
from cloud_asset_audit.models import AuditEvent, IamRecord
from cloud_asset_audit.notify import _http, dispatch, slack, telegram
from cloud_asset_audit.rules import is_critical
from cloud_asset_audit.sinks import csv as csv_sink
from cloud_asset_audit.sinks import google_sheets
from cloud_asset_audit.timeutil import previous_month, to_local
from cloud_asset_audit.tools import gke_maintenance_exclusion as gke


def test_record_uses_dash_for_empty_cells():
    record = IamRecord(cloud="AWS", project="p", project_id="1", user_name="u", user_id="i")
    assert record.headers()[:2] == ["CLOUD", "PROJECT"]
    assert record.row()[5] == "-"


def test_csv_round_trip(tmp_path):
    path = csv_sink.write(demo.records()["iam"], tmp_path)
    rows = list(csv.reader(path.open(encoding="utf-8-sig")))
    assert rows[0][0] == "CLOUD"
    assert len(rows) == 4


def test_csv_skips_empty(tmp_path):
    assert csv_sink.write([], tmp_path) is None


def test_format_requests_cover_header_filter_width_and_freeze():
    kinds = [next(iter(r)) for r in google_sheets.format_requests(7, 10, 5)]
    assert kinds == ["repeatCell", "setBasicFilter", "autoResizeDimensions", "updateSheetProperties"]


def test_upload_replaces_then_formats():
    spreadsheet, worksheet = MagicMock(), MagicMock(id=3, row_count=1)
    spreadsheet.worksheet.return_value = worksheet
    assert google_sheets.upload(demo.records()["vpc"], spreadsheet) == 2
    worksheet.clear.assert_called_once()
    worksheet.resize.assert_called_once_with(rows=3)
    spreadsheet.batch_update.assert_called_once()


@pytest.mark.parametrize(
    ("cloud", "action", "expected"),
    [
        ("AWS", "CreateAccessKey", True),
        ("AWS", "RunInstances", False),
        ("GCP", "SetIamPolicy", True),
        ("TENCENT", "CreateApiKey", True),
    ],
)
def test_critical_rules(cloud, action, expected):
    assert is_critical(cloud, action) is expected


def _event(critical):
    return AuditEvent(
        cloud="AWS",
        project="p",
        project_id="1",
        worker="w",
        action="CreateAccessKey",
        category="KEY",
        critical=critical,
    )


def test_dispatch_alerts_only_on_critical(monkeypatch):
    sent = []
    monkeypatch.setattr(slack, "send", lambda text, env: sent.append(("slack", text)) or True)
    monkeypatch.setattr(telegram, "send", lambda text, a, b: sent.append(("telegram", text)) or True)
    assert dispatch([_event("Y"), _event("")], NotifyConfig()) == 1
    assert [channel for channel, _ in sent] == ["slack", "telegram"]


def test_notifiers_are_quiet_without_configuration(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert slack.send("x") is False
    assert telegram.send("x") is False


def test_post_json_refuses_plain_http():
    with pytest.raises(ValueError, match="HTTPS"):
        _http.post_json("http://example.com/hook", {})


def test_slack_posts_when_configured(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://example.com/hook")
    with patch.object(slack, "post_json") as post:
        assert slack.send("hello") is True
    post.assert_called_once_with("https://example.com/hook", {"text": "hello"})


def test_previous_month_crosses_year():
    start, end = previous_month(datetime(2026, 1, 15, tzinfo=UTC))
    assert (start.year, start.month, end.month) == (2025, 12, 1)


def test_to_local_converts_and_tolerates_missing():
    assert to_local("2026-01-01T00:00:00Z", "Asia/Seoul") == "2026-01-01 09:00:00"
    assert to_local("no_information") == ""


def test_archive_period_wraps_january():
    assert monthly_archive.archive_period(datetime(2026, 1, 3)) == (2025, 12)
    assert monthly_archive.archive_period(datetime(2026, 5, 3)) == (2026, 4)


def test_ensure_folder_reuses_existing():
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {"files": [{"id": "abc"}]}
    assert monthly_archive.ensure_folder(drive, "root", "2026") == "abc"
    drive.files.return_value.create.assert_not_called()


def test_gke_exclusion_is_a_rolling_thirty_days():
    start, end = gke.exclusion_range(datetime(2026, 3, 10, 15, tzinfo=UTC))
    assert (start, end) == ("2026-03-09T00:00:00Z", "2026-04-08T00:00:00Z")


def test_filter_projects_matches_name_or_id():
    records = demo.records()["instance"]
    assert len(collectors.filter_projects(records, ["svc-a-dev"])) == 1
    assert len(collectors.filter_projects(records, ["example-project-b"])) == 1
    assert len(collectors.filter_projects(records, [])) == 3


def test_config_parses_example():
    config = parse(
        {
            "aws": {"role_name": "r", "accounts": [{"name": "a", "account_id": "1"}]},
            "unused": {"exclude_security_group_names": ["x"]},
        }
    )
    assert config.aws.accounts[0].name == "a"
    assert config.unused.exclude_security_group_names == ("x",)


def test_demo_runs_the_whole_pipeline(capsys, tmp_path):
    assert cli.main(["collect", "--demo", "--output", "csv", "--out-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "would alert" in out
    assert (tmp_path / "audit.csv").exists()
    assert (tmp_path / "unused.csv").exists()


def test_cli_requires_config_outside_demo(capsys):
    assert cli.main(["collect", "--resource", "iam"]) == 2
    assert "--config" in capsys.readouterr().err


def test_cli_rejects_unknown_resource():
    assert cli.main(["collect", "--resource", "bogus", "--demo"]) == 2
