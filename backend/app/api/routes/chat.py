"""Chat endpoint — conversational business requirement collection."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.chat_engine import ChatEngine, extract_schema

logger = logging.getLogger(__name__)
router = APIRouter()
engine = ChatEngine()


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user"|"assistant", "content": "..."}]


@router.post("")
async def chat(req: ChatRequest):
    """Streaming chat with DeepSeek to collect business requirements."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    async def generate():
        async for chunk in engine.chat(req.messages):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ExtractSchemaRequest(BaseModel):
    text: str


@router.post("/extract-schema")
async def extract_schema_endpoint(req: ExtractSchemaRequest):
    """Extract BusinessSchema JSON from chat text."""
    schema = extract_schema(req.text)
    if schema:
        return {"schema": schema}
    return {"schema": None}
