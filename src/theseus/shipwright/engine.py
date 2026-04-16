"""The Shipwright engine — core agent loop for AI-powered ERP interaction.

Orchestrates: context assembly → LLM call → tool execution → response.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.llm_gateway.gateway import LLMGateway
from theseus.shipwright.context import ContextBuilder
from theseus.shipwright.conversation.store import ConversationStore
from theseus.shipwright.tools.definitions import get_operator_tools
from theseus.shipwright.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # Prevent infinite tool-calling loops


class ShipwrightEngine:
    """The Shipwright — Theseus ERP's AI assistant.

    Handles conversation management, context assembly, LLM interaction,
    and tool execution in an agent loop.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        gateway: LLMGateway,
        registry: BlueprintRegistry,
        username: str,
        role: str,
        plank_scopes: list[str],
    ) -> None:
        self._session = session
        self._gateway = gateway
        self._registry = registry
        self._conversation_store = ConversationStore(session=session)
        self._tool_executor = ToolExecutor(session=session)
        self._context_builder = ContextBuilder(registry=registry)
        self._username = username
        self._role = role
        self._plank_scopes = plank_scopes

    async def chat(
        self,
        user_message: str,
        conversation_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Process a user message and return the Shipwright's response.

        Returns:
            {
                "message": str — the Shipwright's text response,
                "conversation_id": str — UUID of the conversation,
                "tool_calls_executed": list — tools that were called and their results,
            }
        """
        # Check if LLM is configured
        if not self._gateway.is_configured():
            return {
                "message": "The Shipwright is not configured — no AI provider is set up. "
                           "You can still use the traditional UI to manage your data.",
                "conversation_id": None,
                "tool_calls_executed": [],
            }

        # Get or create conversation
        if conversation_id is None:
            conv = await self._conversation_store.create_conversation(
                crew_member_id=uuid.uuid4(),  # TODO: use actual crew member ID from auth
            )
            conversation_id = conv.id

        # Save user message
        await self._conversation_store.add_message(conversation_id, "user", user_message)

        # Build system prompt
        system_prompt = self._context_builder.build_system_prompt(
            username=self._username,
            role=self._role,
            plank_scopes=self._plank_scopes,
        )

        # Get conversation history
        history = await self._conversation_store.get_messages_for_llm(conversation_id)

        # Build messages for LLM
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history,
        ]

        # Agent loop: LLM → tool calls → execute → feed back → repeat
        tools = get_operator_tools()
        tool_calls_executed: list[dict[str, Any]] = []
        final_message = ""

        for _round in range(MAX_TOOL_ROUNDS):
            response = await self._gateway.complete(
                messages=messages,
                tools=tools,
                temperature=0.3,
            )

            if response.get("error"):
                logger.error("LLM error: %s", response["error"])
                final_message = "I encountered an error processing your request. Please try again."
                break

            # If no tool calls, we have the final response
            if not response["tool_calls"]:
                final_message = response["content"] or ""
                break

            # Execute tool calls
            # Add assistant message with tool calls to history
            assistant_msg = {"role": "assistant", "content": response["content"], "tool_calls": []}
            for tc in response["tool_calls"]:
                assistant_msg["tool_calls"].append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                })
            messages.append(assistant_msg)

            # Save assistant message with tool calls
            await self._conversation_store.add_message(
                conversation_id, "assistant", response["content"],
                tool_calls=response["tool_calls"],
            )

            # Execute each tool and add results
            for tc in response["tool_calls"]:
                result = await self._tool_executor.execute(tc["name"], tc["arguments"])
                tool_calls_executed.append({
                    "tool": tc["name"],
                    "arguments": tc["arguments"],
                    "success": result["success"],
                    "result": result["data"] if result["success"] else result["error"],
                })

                # Add tool result to messages
                tool_result_content = json.dumps(result, default=str)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result_content,
                })

                # Save tool result message
                await self._conversation_store.add_message(
                    conversation_id, "tool", tool_result_content,
                    tool_call_id=tc["id"],
                )
        else:
            final_message = "I've reached the maximum number of tool calls for this request."

        # Save the final assistant response
        await self._conversation_store.add_message(conversation_id, "assistant", final_message)

        await self._session.flush()

        return {
            "message": final_message,
            "conversation_id": str(conversation_id),
            "tool_calls_executed": tool_calls_executed,
        }
