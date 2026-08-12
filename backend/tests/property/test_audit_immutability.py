"""Property 16: Audit Log Immutability.

For any user who is not a platform administrator, all attempts to modify
or delete audit log entries SHALL be denied.

Feature: watari-case-management, Property 16: Audit Log Immutability
**Validates: Requirements 13.5**

Pure predicate test against `audit.deny_modification`.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.auth.context import Role
from src.services.audit import deny_modification


@given(role=st.sampled_from(list(Role)))
def test_only_platform_admin_may_modify(role: Role) -> None:
    if role == Role.PLATFORM_ADMIN:
        assert deny_modification(role) is False
    else:
        assert deny_modification(role) is True


def test_all_non_platform_roles_denied() -> None:
    for role in Role:
        if role is Role.PLATFORM_ADMIN:
            continue
        assert deny_modification(role) is True
