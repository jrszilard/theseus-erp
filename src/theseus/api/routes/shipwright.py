from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import get_registry
from theseus.database import get_session
from theseus.keel.llm_gateway.gateway import LLMGateway
from theseus.shipwright.engine import ShipwrightEngine

router = APIRouter(prefix="/api/v1/shipwright", tags=["shipwright"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str | None
    tool_calls_executed: list[dict[str, Any]] = Field(default_factory=list)


def _get_gateway() -> LLMGateway:
    """Get the LLM gateway. Separated for test mocking."""
    return LLMGateway()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    gateway = _get_gateway()
    registry = get_registry()

    conv_id = uuid.UUID(request.conversation_id) if request.conversation_id else None

    engine = ShipwrightEngine(
        session=session,
        gateway=gateway,
        registry=registry,
        username="default_user",  # TODO: get from auth token
        role="helmsman",
        plank_scopes=[],
    )

    result = await engine.chat(request.message, conversation_id=conv_id)
    return ChatResponse(**result)
