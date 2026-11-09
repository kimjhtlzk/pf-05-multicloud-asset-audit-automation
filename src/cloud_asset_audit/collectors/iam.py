from __future__ import annotations

import csv
import io
import time
from collections import defaultdict
from typing import Any

from cloud_asset_audit.models import IamRecord
from cloud_asset_audit.timeutil import to_local


def _credential_report(client: Any) -> dict[str, dict[str, str]]:
    for _ in range(20):
        if client.generate_credential_report()["State"] == "COMPLETE":
            break
        time.sleep(1)
    content = client.get_credential_report()["Content"].decode("utf-8")
    return {row["user"]: row for row in csv.DictReader(io.StringIO(content))}


def collect_aws(provider: Any, tz: str = "Asia/Seoul") -> list[IamRecord]:
    records: list[IamRecord] = []
    for account, client in provider.global_clients("iam"):
        report = _credential_report(client)
        groups: dict[str, list[str]] = defaultdict(list)
        group_policies: dict[str, list[str]] = defaultdict(list)
        for group in client.list_groups()["Groups"]:
            name = group["GroupName"]
            for user in client.get_group(GroupName=name)["Users"]:
                groups[user["UserName"]].append(name)
            for policy in client.list_attached_group_policies(GroupName=name)["AttachedPolicies"]:
                group_policies[user_group_key(name)].append(policy["PolicyName"])

        for page in client.get_paginator("list_users").paginate():
            for user in page["Users"]:
                name = user["UserName"]
                inline = client.list_user_policies(UserName=name)["PolicyNames"]
                attached = client.list_attached_user_policies(UserName=name)["AttachedPolicies"]
                via_group = [p for g in groups[name] for p in group_policies[user_group_key(g)]]
                permissions = [*inline, *(p["PolicyName"] for p in attached), *via_group]
                keys = client.list_access_keys(UserName=name)["AccessKeyMetadata"]
                row = report.get(name, {})
                records.append(
                    IamRecord(
                        cloud="AWS",
                        project=account.name,
                        project_id=account.account_id,
                        user_name=name,
                        user_id=user["UserId"],
                        user_group=", ".join(groups[name]),
                        permission="\n".join(permissions),
                        user_creation_time=to_local(user["CreateDate"], tz),
                        access_key="\n".join(k["AccessKeyId"] for k in keys),
                        access_key_creation_time="\n".join(to_local(k["CreateDate"], tz) for k in keys),
                        last_login=to_local(row.get("password_last_used"), tz),
                        password_last_changed=to_local(row.get("password_last_changed"), tz),
                    )
                )
    return records


def user_group_key(group: str) -> str:
    return f"group:{group}"


def collect_gcp(provider: Any, tz: str = "Asia/Seoul") -> list[IamRecord]:
    records: list[IamRecord] = []
    projects_client = provider.client("projects")
    admin = provider.client("iam_admin")
    for project in provider.projects:
        display = provider.display_name(project)
        policy = projects_client.get_iam_policy(resource=f"projects/{project}")
        roles: dict[str, list[str]] = defaultdict(list)
        for binding in policy.bindings:
            for member in binding.members:
                roles[member].append(binding.role)

        accounts = {a.email: a for a in admin.list_service_accounts(name=f"projects/{project}")}
        for member, granted in roles.items():
            kind, _, email = member.partition(":")
            keys: list[Any] = []
            unique_id = ""
            if kind == "serviceAccount" and email in accounts:
                unique_id = accounts[email].unique_id
                listed = admin.list_service_account_keys(name=f"projects/{project}/serviceAccounts/{email}")
                keys = [k for k in listed.keys if k.key_type == 1]
            records.append(
                IamRecord(
                    cloud="GCP",
                    project=display,
                    project_id=project,
                    user_name=email,
                    user_id=unique_id,
                    user_group=kind,
                    permission="\n".join(sorted(granted)),
                    access_key="\n".join(k.name.rsplit("/", 1)[-1] for k in keys),
                    access_key_creation_time="\n".join(to_local(k.valid_after_time, tz) for k in keys),
                )
            )
    return records


def collect_tencent(provider: Any) -> list[IamRecord]:
    records: list[IamRecord] = []
    for account in provider.accounts:
        client = provider.client("cam", account, provider.config.regions[0])
        models = provider.models("cam")
        for user in client.ListUsers(models.ListUsersRequest()).Data:
            groups_req = models.ListGroupsForUserRequest()
            groups_req.Uid = user.Uid
            groups = client.ListGroupsForUser(groups_req).GroupInfo or []
            policies_req = models.ListAttachedUserAllPoliciesRequest()
            policies_req.TargetUin = user.Uin
            policies_req.Rp = 200
            policies_req.Page = 1
            policies_req.AttachType = 0
            policies = client.ListAttachedUserAllPolicies(policies_req).PolicyList or []
            keys_req = models.ListAccessKeysRequest()
            keys_req.TargetUin = user.Uin
            keys = client.ListAccessKeys(keys_req).AccessKeys or []
            records.append(
                IamRecord(
                    cloud="TENCENT",
                    project=account.name,
                    project_id=account.account_id,
                    user_name=user.Name,
                    user_id=str(user.Uin),
                    user_group=", ".join(g.GroupName for g in groups),
                    permission="\n".join(p.PolicyName for p in policies),
                    user_creation_time=getattr(user, "CreateTime", "") or "",
                    access_key="\n".join(k.AccessKeyId for k in keys),
                    access_key_creation_time="\n".join(k.CreateTime for k in keys),
                )
            )
    return records
