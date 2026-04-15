from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from theseus.config import settings
from theseus.keel.auth.models import CrewMember, CrewMemberRecord, CrewRole

ALGORITHM = "HS256"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_crew_member(self, *, username: str, password: str, display_name: str,
                                  role: CrewRole, plank_scopes: list[str] | None = None) -> CrewMemberRecord:
        existing = await self._get_by_username(username)
        if existing is not None:
            raise ValueError(f"Username '{username}' already exists")
        member = CrewMember(username=username, password_hash=_hash_password(password),
                           display_name=display_name, role=role.value, plank_scopes=plank_scopes or [])
        self._session.add(member)
        await self._session.flush()
        return CrewMemberRecord.model_validate(member)

    async def authenticate(self, username: str, password: str) -> CrewMemberRecord | None:
        member = await self._get_by_username(username)
        if member is None or not _verify_password(password, member.password_hash):
            return None
        return CrewMemberRecord.model_validate(member)

    def create_access_token(self, member: CrewMemberRecord) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {"sub": str(member.id), "username": member.username, "role": member.role.value,
                   "plank_scopes": member.plank_scopes, "exp": expire}
        return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        except JWTError:
            return None

    async def _get_by_username(self, username: str) -> CrewMember | None:
        stmt = select(CrewMember).where(CrewMember.username == username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
