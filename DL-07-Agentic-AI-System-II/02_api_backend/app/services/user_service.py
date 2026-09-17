"""Map a verified token to our user record (just-in-time provisioning, D-43)."""

from __future__ import annotations

from pydantic import SecretStr

from app.core.crypto import keyed_hash
from app.core.security import Principal
from app.services.ports import RecommendationRepository, UserRef


class UserService:
    def __init__(
        self, repository: RecommendationRepository, pseudonym_secret: SecretStr | None
    ) -> None:
        self._repo = repository
        self._secret = pseudonym_secret

    async def resolve(self, principal: Principal) -> UserRef:
        # The pseudonym is what the Agent and feedback see; it cannot be reversed to the user.
        return await self._repo.get_or_create_user(
            principal.issuer,
            principal.subject,
            pseudonym=lambda user_id: keyed_hash(self._secret, str(user_id)),
        )
