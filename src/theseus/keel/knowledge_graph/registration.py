from __future__ import annotations

import logging

from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph

logger = logging.getLogger(__name__)


async def register_blueprints_in_graph(
    registry: BlueprintRegistry,
    graph: PostgresKnowledgeGraph,
) -> None:
    """Register all Blueprint entity types and relationships in the Knowledge Graph.

    Idempotent — skips entities and relationships that are already registered.
    """
    # First pass: register all entity types
    for bp in registry.all():
        existing = await graph.get_entity_type(bp.full_name)
        if existing is None:
            await graph.register_entity_type(
                plank=bp.plank,
                entity=bp.entity,
                description=bp.description,
            )
            logger.info("Graph: registered entity type %s", bp.full_name)

    # Second pass: register relationships (all entity types must exist first)
    for bp in registry.all():
        if not bp.relations:
            continue
        for rel_name, relation in bp.relations.items():
            # Only register if the target entity type is also registered
            target = await graph.get_entity_type(relation.target)
            if target is None:
                logger.warning(
                    "Graph: skipping relationship %s.%s -> %s (target not registered)",
                    bp.full_name, rel_name, relation.target,
                )
                continue

            # Check if this edge already exists (simple dedup by source+target+name)
            existing_related = await graph.get_related_types(bp.full_name)
            already_connected = any(
                r.full_name == relation.target for r in existing_related
            )
            if not already_connected:
                await graph.register_relationship_type(
                    source=bp.full_name,
                    target=relation.target,
                    relation_name=rel_name,
                    relation_type=relation.type.value,
                )
                logger.info(
                    "Graph: registered relationship %s -[%s]-> %s",
                    bp.full_name, rel_name, relation.target,
                )
