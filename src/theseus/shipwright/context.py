"""Context assembly for the Shipwright.

Builds the system prompt from 4 layers:
1. Keel Context (static) — what Theseus is and how it works
2. Ship Context (per-business) — what Blueprints/entities exist
3. Crew Context (per-user) — role, permissions, preferences
4. Voyage Context (per-session) — added dynamically during conversation
"""
from __future__ import annotations

from theseus.keel.blueprint_engine.registry import BlueprintRegistry


class ContextBuilder:
    """Builds the Shipwright's system prompt from layered context."""

    def __init__(self, registry: BlueprintRegistry | None = None) -> None:
        self._registry = registry

    def build_system_prompt(
        self,
        *,
        username: str,
        role: str,
        plank_scopes: list[str],
    ) -> str:
        """Build the complete system prompt combining all context layers."""
        sections = [
            self.build_keel_context(),
            self.build_ship_context(),
            self.build_crew_context(username=username, role=role, plank_scopes=plank_scopes),
        ]
        return "\n\n---\n\n".join(sections)

    def build_keel_context(self) -> str:
        """Layer 1: Static context about what Theseus is."""
        return """You are the Shipwright — the AI assistant for Theseus ERP.

Theseus ERP is an open-source, AI-first ERP for small manufacturing and trade businesses.
Named after the Ship of Theseus: every module (Plank) can be rebuilt, and no two
implementations are alike.

Your role is to help users manage their business operations through natural language.
You can create, query, and update records across all Planks (modules) in the system.

Key terminology:
- Plank = a module (e.g., contacts, inventory, invoicing)
- Blueprint = the YAML definition of an entity type
- Crew = users of the system
- Helmsman = admin, Bosun = department lead, Deckhand = daily user

When users ask you to do something, use the available tools to interact with the system.
Always confirm what you did after completing an action. Be concise and helpful."""

    def build_ship_context(self) -> str:
        """Layer 2: Per-business context — what entities exist."""
        if not self._registry:
            return "No Blueprints are currently loaded."

        lines = ["## Available Entity Types\n"]
        current_plank = ""
        for bp in sorted(self._registry.all(), key=lambda b: b.full_name):
            if bp.plank != current_plank:
                current_plank = bp.plank
                lines.append(f"\n### Plank: {bp.plank}")

            fields_summary = ", ".join(bp.fields.keys())
            lines.append(f"- **{bp.full_name}**: {bp.description}")
            lines.append(f"  Fields: {fields_summary}")

            if bp.relations:
                rels = [f"{name} -> {rel.target}" for name, rel in bp.relations.items()]
                lines.append(f"  Relations: {', '.join(rels)}")

        return "\n".join(lines)

    def build_crew_context(
        self,
        *,
        username: str,
        role: str,
        plank_scopes: list[str],
    ) -> str:
        """Layer 3: Per-user context — role and permissions."""
        lines = [f"## Current User\n"]
        lines.append(f"- Username: {username}")
        lines.append(f"- Role: {role}")

        if role == "helmsman":
            lines.append("- Access: Full access to all Planks")
        elif plank_scopes:
            lines.append(f"- Plank access: {', '.join(plank_scopes)}")
        else:
            lines.append("- Plank access: All Planks")

        return "\n".join(lines)
