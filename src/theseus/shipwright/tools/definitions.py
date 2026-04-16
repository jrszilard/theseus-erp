"""Tool definitions for the Shipwright.

Each tool is a Pydantic model that validates arguments and generates
OpenAI-compatible function schemas for LLM consumption.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShipwrightTool(BaseModel):
    """Base class for all Shipwright tools."""

    @classmethod
    def tool_name(cls) -> str:
        raise NotImplementedError

    @classmethod
    def tool_description(cls) -> str:
        raise NotImplementedError

    @classmethod
    def to_openai_schema(cls) -> dict[str, Any]:
        """Generate OpenAI-compatible tool schema from the Pydantic model."""
        schema = cls.model_json_schema()
        # Remove Pydantic metadata keys not needed by OpenAI
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": cls.tool_name(),
                "description": cls.tool_description(),
                "parameters": schema,
            },
        }


class CreateEntityTool(ShipwrightTool):
    """Create a new entity in any Plank."""
    plank: str = Field(description="The plank name (e.g., 'contacts', 'inventory', 'invoicing')")
    entity: str = Field(description="The entity type (e.g., 'Contact', 'StockItem', 'Invoice')")
    data: dict[str, Any] = Field(description="The entity data as key-value pairs")

    @classmethod
    def tool_name(cls) -> str:
        return "create_entity"

    @classmethod
    def tool_description(cls) -> str:
        return "Create a new entity record in the specified plank. Use this for creating contacts, inventory items, invoices, etc."


class QueryEntitiesTool(ShipwrightTool):
    """Query entities from any Plank."""
    plank: str = Field(description="The plank name")
    entity: str = Field(description="The entity type")
    filters: dict[str, Any] = Field(default_factory=dict, description="Optional filters as key-value pairs")

    @classmethod
    def tool_name(cls) -> str:
        return "query_entities"

    @classmethod
    def tool_description(cls) -> str:
        return "List or search entities in a plank. Returns matching records."


class GetEntityTool(ShipwrightTool):
    """Get a specific entity by ID."""
    plank: str = Field(description="The plank name")
    entity: str = Field(description="The entity type")
    entity_id: str = Field(description="The UUID of the entity to retrieve")

    @classmethod
    def tool_name(cls) -> str:
        return "get_entity"

    @classmethod
    def tool_description(cls) -> str:
        return "Get a specific entity by its ID. Returns the full record with all fields."


class UpdateEntityTool(ShipwrightTool):
    """Update an existing entity."""
    plank: str = Field(description="The plank name")
    entity: str = Field(description="The entity type")
    entity_id: str = Field(description="The UUID of the entity to update")
    data: dict[str, Any] = Field(description="The fields to update as key-value pairs")

    @classmethod
    def tool_name(cls) -> str:
        return "update_entity"

    @classmethod
    def tool_description(cls) -> str:
        return "Update fields on an existing entity. Only the provided fields are changed."


class GetStockLevelTool(ShipwrightTool):
    """Get the current stock level for an inventory item."""
    stock_item_id: str = Field(description="The UUID of the stock item")

    @classmethod
    def tool_name(cls) -> str:
        return "get_stock_level"

    @classmethod
    def tool_description(cls) -> str:
        return "Get the current stock level for an inventory item. Computed from movement history."


class SearchContactsTool(ShipwrightTool):
    """Search for contacts by name or type."""
    name_contains: str | None = Field(default=None, description="Search contacts whose name contains this text")
    contact_type: str | None = Field(default=None, description="Filter by contact type: customer, supplier, employee, other")

    @classmethod
    def tool_name(cls) -> str:
        return "search_contacts"

    @classmethod
    def tool_description(cls) -> str:
        return "Search for contacts by name and/or type. Returns matching contact records."


# Registry of all Operator tools
OPERATOR_TOOLS: list[type[ShipwrightTool]] = [
    CreateEntityTool,
    QueryEntitiesTool,
    GetEntityTool,
    UpdateEntityTool,
    GetStockLevelTool,
    SearchContactsTool,
]


def get_operator_tools() -> list[dict[str, Any]]:
    """Get all Operator tool schemas in OpenAI format."""
    return [tool.to_openai_schema() for tool in OPERATOR_TOOLS]
