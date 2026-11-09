# Refactor notes

## Feature map

| Original feature | Location in this repository |
|---|---|
| IAM, firewall, instance, load balancer, VPC collection | `collectors/` |
| Audit event collection for three clouds | `collectors/audit_log.py` |
| Unused IP, security group, disk, firewall detection | `collectors/unused.py` |
| Common fields per resource type | `models.py` |
| Cross-account roles and impersonation | `providers/` |
| Sheet upload with header style, filter, width, frozen header | `sinks/google_sheets.py` |
| Refresh a single project | `cloud-audit collect --project` |
| Monthly archive to year and month folders | `jobs/monthly_archive.py` |
| Image and snapshot create and delete | `tools/snapshot_control.py` |
| Rolling GKE maintenance exclusion | `tools/gke_maintenance_exclusion.py` |

## What changed and why

| Change | Reason |
|---|---|
| About 9,800 lines became about 2151 | Shared upload, login, and model code now exists once |
| Key files replaced by standard credential chains | See ADR-003 |
| Five audit classes merged into `AuditEvent` | One table for reviewers |
| Tests added with moto and mocks | No test coverage existed |
| CSV output and demo mode added | Usable without a sheet or a cloud account |
| Slack and Telegram alerts rewritten | The production alerting code was not part of the earlier scripts |
| Several security group name exclusions moved to settings | They were specific to one environment |
