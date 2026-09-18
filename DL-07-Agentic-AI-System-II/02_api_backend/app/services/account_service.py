"""Second phase of account deletion, run by the `delete_account` task (D-79)."""

from __future__ import annotations

from uuid import UUID

from app.core.logging import get_logger
from app.domain.enums import ActorType, AuditResult
from app.services.ports import AuditEntry, AuditPort, UserRepository

log = get_logger(__name__)


class AccountService:
    def __init__(self, *, users: UserRepository, audit: AuditPort) -> None:
        self._users = users
        self._audit = audit

    async def delete(self, user_id: UUID, *, correlation_id: str) -> bool:
        """Delete the user's rows; False when they are already gone (safe to run twice)."""
        pseudonym = await self._users.delete_account(user_id)
        if pseudonym is None:
            log.info("account_already_deleted")
            return False
        # The audit row names the pseudonym, never the login subject (data design 6.2).
        await self._audit.write(
            AuditEntry(
                actor_type=ActorType.SYSTEM,
                actor_ref=pseudonym,
                action="user.delete",
                target_type=None,
                target_id=None,
                result=AuditResult.SUCCESS,
                correlation_id=correlation_id,
                ip_hash=None,
                metadata={},
            )
        )
        log.info("account_deleted")
        return True
