from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from theseus.database import Base


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plank: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(201), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    __table_args__ = (UniqueConstraint("plank", "entity", name="uq_graph_nodes_plank_entity"),)


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    source_full_name: Mapped[str] = mapped_column(String(201), nullable=False, index=True)
    target_full_name: Mapped[str] = mapped_column(String(201), nullable=False, index=True)
    relation_name: Mapped[str] = mapped_column(String(100), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)


class GraphNodeRecord(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    plank: str
    entity: str
    full_name: str
    description: str


class GraphEdgeRecord(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    source_full_name: str
    target_full_name: str
    relation_name: str
    relation_type: str
