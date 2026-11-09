# Tencent Cloud permissions

Attach these CAM preset policies to the role or sub-account. All of them are read-only.

| Policy | Used for |
|---|---|
| `QcloudCVMReadOnlyAccess` | Instances |
| `QcloudVPCReadOnlyAccess` | VPCs, subnets, security groups, addresses |
| `QcloudCLBReadOnlyAccess` | Load balancers |
| `QcloudCBSReadOnlyAccess` | Disks |
| `QcloudCamReadOnlyAccess` | Users, groups, policies, API keys |
| `QcloudAuditReadOnlyAccess` | CloudAudit events |

Provide credentials through the `TENCENTCLOUD_SECRET_ID` and `TENCENTCLOUD_SECRET_KEY` environment variables.
