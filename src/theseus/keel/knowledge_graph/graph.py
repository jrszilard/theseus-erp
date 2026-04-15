from __future__ import annotations
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from theseus.keel.knowledge_graph.models import GraphEdge, GraphEdgeRecord, GraphNode, GraphNodeRecord


class PostgresKnowledgeGraph:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_entity_type(self, plank: str, entity: str, description: str) -> GraphNodeRecord:
        node = GraphNode(plank=plank, entity=entity, full_name=f"{plank}.{entity}", description=description)
        self._session.add(node)
        await self._session.flush()
        return GraphNodeRecord.model_validate(node)

    async def register_relationship_type(self, source: str, target: str, relation_name: str, relation_type: str) -> GraphEdgeRecord:
        source_node = await self._get_node(source)
        target_node = await self._get_node(target)
        if source_node is None:
            raise ValueError(f"Source entity type not found: {source}")
        if target_node is None:
            raise ValueError(f"Target entity type not found: {target}")
        edge = GraphEdge(source_id=source_node.id, target_id=target_node.id,
                         source_full_name=source, target_full_name=target,
                         relation_name=relation_name, relation_type=relation_type)
        self._session.add(edge)
        await self._session.flush()
        return GraphEdgeRecord.model_validate(edge)

    async def get_entity_type(self, full_name: str) -> GraphNodeRecord | None:
        node = await self._get_node(full_name)
        return GraphNodeRecord.model_validate(node) if node else None

    async def get_related_types(self, full_name: str) -> list[GraphNodeRecord]:
        edges_stmt = select(GraphEdge).where(or_(GraphEdge.source_full_name == full_name, GraphEdge.target_full_name == full_name))
        result = await self._session.execute(edges_stmt)
        edges = result.scalars().all()
        related_names: set[str] = set()
        for edge in edges:
            related_names.add(edge.target_full_name if edge.source_full_name == full_name else edge.source_full_name)
        if not related_names:
            return []
        nodes_stmt = select(GraphNode).where(GraphNode.full_name.in_(related_names))
        result = await self._session.execute(nodes_stmt)
        return [GraphNodeRecord.model_validate(n) for n in result.scalars().all()]

    async def get_types_by_plank(self, plank: str) -> list[GraphNodeRecord]:
        stmt = select(GraphNode).where(GraphNode.plank == plank)
        result = await self._session.execute(stmt)
        return [GraphNodeRecord.model_validate(n) for n in result.scalars().all()]

    async def _get_node(self, full_name: str) -> GraphNode | None:
        stmt = select(GraphNode).where(GraphNode.full_name == full_name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
