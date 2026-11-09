# Design decisions

## ADR-001: One schema across clouds

- **Context:** Each cloud returns a different shape for the same concept.
- **Decision:** Normalize every record into one dataclass per resource type.
- **Reason:** A reviewer can sort and filter one table instead of comparing three.
- **Alternatives:** Keeping raw JSON per cloud, which moves the comparison work to the reader.

## ADR-002: One collector file per resource, not per cloud

- **Context:** The previous layout repeated the same upload and login code in every folder.
- **Decision:** `collectors/<resource>.py` holds one function per cloud, and everything shared lives once.
- **Reason:** Comparing how three clouds answer the same question is the most common review task.
- **Trade-off:** Files for complex resources are longer.

## ADR-003: Standard credential chains only

- **Context:** Key files on disk can leak.
- **Decision:** AWS uses profiles or roles, GCP uses Application Default Credentials with impersonation, Tencent Cloud uses environment variables with an optional CAM role.
- **Reason:** Nothing secret needs to exist in the project directory.

## ADR-004: Critical events are data, not code

- **Context:** The list of events worth waking someone up for changes over time.
- **Decision:** Keep the list in `rules/critical_events.yaml`.
- **Reason:** A security reviewer can change or audit it without reading Python.

## ADR-005: A demo mode with fake data

- **Context:** Nobody can evaluate this tool without three cloud accounts.
- **Decision:** `--demo` runs the same output path with fake records.
- **Reason:** It needs no credentials and makes no network calls.
