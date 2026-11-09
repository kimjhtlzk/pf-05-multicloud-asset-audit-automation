# GCP permissions

Grant these roles to the service account the tool impersonates. All of them are read-only.

| Role | Used for |
|---|---|
| `roles/compute.viewer` | Instances, disks, firewalls, addresses, subnets, load balancers |
| `roles/iam.securityReviewer` | IAM policy and service account keys |
| `roles/logging.viewer` | Audit log queries |
| `roles/browser` | Project display name |

These two optional tools make changes and need their own, separately granted roles:

| Tool | Role |
|---|---|
| `cloud-audit snapshot` | `roles/compute.storageAdmin` |
| `cloud-audit gke-exclusion` | `roles/container.clusterAdmin` |

The caller needs `roles/iam.serviceAccountTokenCreator` on the impersonated account.
