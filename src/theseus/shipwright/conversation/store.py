from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.shipwright.conversation.models import (
    Conversation,
    ConversationRecord,
    Message,
    MessageRecord,
)


class ConversationStore:
    """Persists Shipwright conversations and messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(self, crew_member_id: uuid.UUID) -> ConversationRecord:
        conv = Conversation(crew_member_id=crew_member_id)
        self._session.add(conv)
        await self._session.flush()
        return ConversationRecord(
            id=conv.id,
            crew_member_id=conv.crew_member_id,
            messages=[],
        )

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
    ) -> MessageRecord:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
        )
        self._session.add(msg)
        await self._session.flush()
        return MessageRecord.model_validate(msg)

    async def get_messages(self, conversation_id: uuid.UUID) -> list[MessageRecord]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [MessageRecord.model_validate(m) for m in result.scalars().all()]

    async def get_messages_for_llm(self, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
        """Get messages formatted for LLM consumption (OpenAI message format)."""
        messages = await self.get_messages(conversation_id)
        llm_msgs: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                entry["content"] = msg.content
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            llm_msgs.append(entry)
        return llm_msgs
