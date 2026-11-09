"""Command line entry point: cloud-audit."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cloud_asset_audit import collectors
from cloud_asset_audit.config import Config, load
from cloud_asset_audit.models import AuditEvent, Record
from cloud_asset_audit.notify import critical_only, dispatch, format_alert
from cloud_asset_audit.sinks import csv as csv_sink


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cloud-audit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="Collect one resource type, or all of them")
    collect.add_argument(
        "--resource", default="all", help=f"all or one of: {', '.join(collectors.RESOURCES)}"
    )
    collect.add_argument("--cloud", default="aws,gcp,tencent", help="Comma-separated list of clouds")
    collect.add_argument(
        "--project", action="append", default=[], help="Refresh only this project (repeatable)"
    )
    collect.add_argument("--config", help="Path to the YAML config")
    collect.add_argument("--output", choices=("table", "csv", "sheets"), default="table")
    collect.add_argument("--out-dir", default="output")
    collect.add_argument("--notify", action="store_true", help="Send alerts for critical audit events")
    collect.add_argument("--demo", action="store_true", help="Use fake data. No credentials needed")

    archive = sub.add_parser("archive", help="Back up audit sheets to Google Drive by year and month")
    archive.add_argument("--config", required=True)

    gke = sub.add_parser("gke-exclusion", help="Renew the rolling GKE maintenance exclusion")
    gke.add_argument("--project", required=True)
    gke.add_argument("--location", required=True)
    gke.add_argument("--cluster", required=True)
    gke.add_argument("--config", required=True)

    snapshot = sub.add_parser("snapshot", help="Create or delete a GCP image")
    snapshot.add_argument("action", choices=("create", "delete"))
    snapshot.add_argument("--project", required=True)
    snapshot.add_argument("--image", required=True)
    snapshot.add_argument("--zone")
    snapshot.add_argument("--disk")
    snapshot.add_argument("--config", required=True)
    return parser


def print_table(records: Sequence[Record], columns: int = 6, width: int = 20) -> None:
    if not records:
        return
    print(f"\n{records[0].sheet} ({len(records)})")
    headers = records[0].headers()[:columns]
    print("  ".join(h[:width].ljust(width) for h in headers))
    for record in records:
        cells = [str(c).replace("\n", " ")[: width - 1] for c in record.row()[:columns]]
        print("  ".join(c.ljust(width) for c in cells))


def providers_for(config: Config, clouds: Sequence[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    if "aws" in clouds:
        from cloud_asset_audit.providers.aws import AwsProvider

        result["aws"] = AwsProvider(config.aws)
    if "gcp" in clouds:
        from cloud_asset_audit.providers.gcp import GcpProvider

        result["gcp"] = GcpProvider(config.gcp)
    if "tencent" in clouds:
        from cloud_asset_audit.providers.tencent import TencentProvider

        result["tencent"] = TencentProvider(config.tencent)
    return result


def run_collect(args: argparse.Namespace) -> int:
    resources = list(collectors.RESOURCES) if args.resource == "all" else [args.resource]
    unknown = set(resources) - set(collectors.RESOURCES)
    if unknown:
        print(f"Unknown resource: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    clouds = [c.strip() for c in args.cloud.split(",") if c.strip()]

    config = Config()
    if args.demo:
        from cloud_asset_audit import demo

        fake = demo.records()
        results = {r: fake[r] for r in resources}
    else:
        if not args.config:
            print("--config is required unless --demo is set", file=sys.stderr)
            return 2
        config = load(args.config)
        providers = providers_for(config, clouds)
        results = {r: collectors.collect(r, providers, clouds) for r in resources}

    spreadsheet = None
    for resource, records in results.items():
        records = collectors.filter_projects(records, args.project)
        if args.output == "csv":
            path = csv_sink.write(records, Path(args.out_dir))
            if path:
                print(f"wrote {path} ({len(records)} rows)")
        elif args.output == "sheets":
            from cloud_asset_audit.sinks import google_sheets

            spreadsheet = spreadsheet or google_sheets.open_spreadsheet(config.sheets.spreadsheet_id)
            print(f"{resource}: uploaded {google_sheets.upload(records, spreadsheet)} rows")
        else:
            print_table(records)

    events = [r for r in results.get("audit_log", []) if isinstance(r, AuditEvent)]
    if args.demo:
        for event in critical_only(events):
            print(f"\nwould alert Slack and Telegram:\n{format_alert(event)}")
    elif args.notify:
        print(f"alerted on {dispatch(events, config.notify)} critical events")
    return 0


def run_archive(args: argparse.Namespace) -> int:
    import google.auth
    from googleapiclient.discovery import build

    from cloud_asset_audit.jobs import monthly_archive
    from cloud_asset_audit.sinks import google_sheets

    config = load(args.config)
    credentials, _ = google.auth.default(scopes=google_sheets.SCOPES)
    drive = build("drive", "v3", credentials=credentials)
    spreadsheet = google_sheets.open_spreadsheet(config.sheets.spreadsheet_id)
    done = monthly_archive.run(
        spreadsheet, drive, config.sheets.archive_folder_id, config.sheets.archive_sheets
    )
    print(f"archived: {', '.join(done)}")
    return 0


def run_gke(args: argparse.Namespace) -> int:
    from cloud_asset_audit.providers.gcp import GcpProvider
    from cloud_asset_audit.tools import gke_maintenance_exclusion

    client = GcpProvider(load(args.config).gcp).client("container")
    gke_maintenance_exclusion.apply(client, args.project, args.location, args.cluster)
    print(f"renewed exclusion on {args.cluster}")
    return 0


def run_snapshot(args: argparse.Namespace) -> int:
    from cloud_asset_audit.providers.gcp import GcpProvider
    from cloud_asset_audit.tools import snapshot_control

    provider = GcpProvider(load(args.config).gcp)
    if args.action == "create":
        if not args.zone or not args.disk:
            print("--zone and --disk are required for create", file=sys.stderr)
            return 2
        snapshot_control.gcp_create_image(provider, args.project, args.zone, args.disk, args.image)
    else:
        snapshot_control.gcp_delete_image(provider, args.project, args.image)
    print(f"{args.action}d image {args.image}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "collect": run_collect,
        "archive": run_archive,
        "gke-exclusion": run_gke,
        "snapshot": run_snapshot,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
