import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.shipwright.conversation.store import ConversationStore


class TestConversationStore:
    @pytest.mark.asyncio
    async def test_create_conversation(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        assert conv.id is not None
        assert len(conv.messages) == 0

    @pytest.mark.asyncio
    async def test_add_message(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        msg = await store.add_message(
            conversation_id=conv.id,
            role="user",
            content="Hello Shipwright",
        )
        assert msg.role == "user"
        assert msg.content == "Hello Shipwright"

    @pytest.mark.asyncio
    async def test_add_assistant_message_with_tool_calls(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        msg = await store.add_message(
            conversation_id=conv.id,
            role="assistant",
            content=None,
            tool_calls=[{"id": "call_1", "name": "create_entity", "arguments": {"plank": "contacts"}}],
        )
        assert msg.role == "assistant"
        assert len(msg.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_add_tool_result_message(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        msg = await store.add_message(
            conversation_id=conv.id,
            role="tool",
            content='{"success": true}',
            tool_call_id="call_1",
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_1"

    @pytest.mark.asyncio
    async def test_get_messages(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        await store.add_message(conv.id, "user", "Hello")
        await store.add_message(conv.id, "assistant", "Hi there!")
        await store.add_message(conv.id, "user", "Create a contact")

        messages = await store.get_messages(conv.id)
        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].content == "Create a contact"

    @pytest.mark.asyncio
    async def test_get_messages_as_llm_format(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        await store.add_message(conv.id, "user", "Hello")
        await store.add_message(conv.id, "assistant", "Hi!")

        llm_messages = await store.get_messages_for_llm(conv.id)
        assert llm_messages == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
