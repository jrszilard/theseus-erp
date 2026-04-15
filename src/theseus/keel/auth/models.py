from __future__ import annotations
import uuid
from enum import StrEnum
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from theseus.database import Base


class CrewRole(StrEnum):
    HELMSMAN = "helmsman"
    BOSUN = "bosun"
    DECKHAND = "deckhand"


class CrewMember(Base):
    __tablename__ = "crew_members"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    plank_scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class CrewMemberRecord(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    username: str
    password_hash: str
    display_name: str
    role: CrewRole
    plank_scopes: list[str]
    is_active: bool
