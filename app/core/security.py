import re
from dataclasses import dataclass, field
from typing import Any

PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"show\s+(the\s+)?system\s+prompt",
    r"developer\s+message",
]


@dataclass(frozen=True)
class UserContext:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)


# Local demo identities. In production, replace this registry with a
# verified JWT/OAuth2/SSO identity provider and server-side user directory.
DEMO_USERS = {
    "admin_demo": UserContext(
        user_id="admin_demo",
        tenant_id="tenant_demo",
        roles=("admin",),
        permissions=(
            "documents:read",
            "documents:write",
            "compliance:analyze",
            "audit:read",
            "users:manage",
        ),
    ),
    "analyst_demo": UserContext(
        user_id="analyst_demo",
        tenant_id="tenant_demo",
        roles=("analyst",),
        permissions=("documents:read", "compliance:analyze"),
    ),
    "manager_demo": UserContext(
        user_id="manager_demo",
        tenant_id="tenant_demo",
        roles=("manager",),
        permissions=(
            "documents:read",
            "documents:write",
            "compliance:analyze",
            "audit:read",
        ),
    ),
    "auditor_demo": UserContext(
        user_id="auditor_demo",
        tenant_id="tenant_demo",
        roles=("auditor",),
        permissions=("documents:read", "compliance:analyze", "audit:read"),
    ),
    "company_b_analyst": UserContext(
        user_id="company_b_analyst",
        tenant_id="tenant_b",
        roles=("analyst",),
        permissions=("documents:read", "compliance:analyze"),
    ),
}


def is_prompt_injection(text: str) -> bool:
    value = text.lower()
    return any(re.search(pattern, value) for pattern in PATTERNS)


def require_tenant(tenant_id: str) -> str:
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required")
    return tenant_id.strip()


def authenticate_demo_user(user_id: str) -> UserContext:
    if not user_id or not user_id.strip():
        raise PermissionError("Authentication required")

    user = DEMO_USERS.get(user_id.strip())
    if user is None:
        raise PermissionError("Unknown user identity")

    return user


def authorize(user: UserContext, permission: str) -> None:
    if permission not in user.permissions:
        raise PermissionError(
            f"User is not authorized for '{permission}'"
        )


def normalize_list(values: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = values.split(",")
    return [str(value).strip() for value in values if str(value).strip()]


def access_flag_key(prefix: str, value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", value.strip())
    return f"{prefix}_{safe}"


def normalize_access_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    result = dict(metadata)

    scope = str(result.get("access_scope", "tenant")).strip().lower()
    if scope not in {"tenant", "roles", "users"}:
        raise ValueError(
            "access_scope must be one of: tenant, roles, users"
        )

    result["access_scope"] = scope
    result["allowed_roles"] = normalize_list(result.get("allowed_roles"))
    result["allowed_users"] = normalize_list(result.get("allowed_users"))

    if scope == "roles" and not result["allowed_roles"]:
        raise ValueError(
            "allowed_roles is required when access_scope='roles'"
        )

    if scope == "users" and not result["allowed_users"]:
        raise ValueError(
            "allowed_users is required when access_scope='users'"
        )

    if scope != "roles":
        result["allowed_roles"] = []
    if scope != "users":
        result["allowed_users"] = []

    return result


def can_access_document(user: UserContext, metadata: dict[str, Any]) -> bool:
    if metadata.get("tenant_id") != user.tenant_id:
        return False

    if "admin" in user.roles:
        return True

    scope = metadata.get("access_scope", "tenant")

    if scope == "tenant":
        return True

    if scope == "roles":
        allowed_roles = set(normalize_list(metadata.get("allowed_roles")))
        return bool(allowed_roles.intersection(user.roles)) or any(
            bool(metadata.get(access_flag_key("access_role", role), False))
            for role in user.roles
        )

    if scope == "users":
        allowed_users = set(normalize_list(metadata.get("allowed_users")))
        return user.user_id in allowed_users or bool(metadata.get(access_flag_key("access_user", user.user_id), False))

    return False


def authorized_documents(user: UserContext, documents: list[dict]) -> list[dict]:
    return [
        document
        for document in documents
        if can_access_document(user, document.get("metadata", {}))
    ]
