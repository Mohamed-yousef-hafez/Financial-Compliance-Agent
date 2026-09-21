from app.core.security import (
    UserContext,
    authorize,
    can_access_document,
    normalize_access_metadata,
)


def user(tenant="tenant_a", user_id="user_1", roles=("analyst",)):
    return UserContext(
        user_id=user_id,
        tenant_id=tenant,
        roles=roles,
        permissions=("documents:read", "compliance:analyze"),
    )


def test_cross_tenant_access_denied():
    assert not can_access_document(
        user("tenant_a"),
        {"tenant_id": "tenant_b", "access_scope": "tenant"},
    )


def test_tenant_wide_document_allowed():
    assert can_access_document(
        user("tenant_a"),
        {"tenant_id": "tenant_a", "access_scope": "tenant"},
    )


def test_role_restricted_document():
    metadata = normalize_access_metadata(
        {
            "tenant_id": "tenant_a",
            "access_scope": "roles",
            "allowed_roles": ["manager"],
        }
    )
    metadata["tenant_id"] = "tenant_a"
    assert not can_access_document(user(roles=("analyst",)), metadata)
    assert can_access_document(user(roles=("manager",)), metadata)


def test_user_restricted_document():
    metadata = normalize_access_metadata(
        {
            "tenant_id": "tenant_a",
            "access_scope": "users",
            "allowed_users": ["user_2"],
        }
    )
    assert not can_access_document(user(user_id="user_1"), metadata)
    assert can_access_document(user(user_id="user_2"), metadata)


def test_permission_denied():
    restricted = UserContext(
        user_id="user_1",
        tenant_id="tenant_a",
        roles=("viewer",),
        permissions=("documents:read",),
    )
    try:
        authorize(restricted, "compliance:analyze")
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
