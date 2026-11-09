# Architecture

| Layer | Path | Responsibility |
|---|---|---|
| Entry | `cli.py` | Parses commands and connects the layers |
| Settings | `config.py` | YAML accounts, regions, sheet IDs, names of secret variables |
| Identity | `providers/` | Sessions from the standard credential chain, cross-account roles, impersonation |
| Collection | `collectors/` | One file per resource type, one function per cloud |
| Schema | `models.py` | One dataclass per resource type |
| Rules | `rules/critical_events.yaml` | Which events cause an alert |
| Output | `sinks/`, `notify/`, `jobs/` | Sheets, CSV, alerts, monthly archive |
| Operations | `tools/` | Snapshot control and GKE maintenance exclusion |

## Adding a resource type

1. Add a dataclass to `models.py`.
2. Add `collectors/<name>.py` with `collect_aws`, `collect_gcp`, and `collect_tencent`.
3. Add the name to `RESOURCES` in `collectors/__init__.py`.

Everything else, including sheets, CSV, and the CLI, works without changes.
