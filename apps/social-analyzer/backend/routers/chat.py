"""
Chat router — SSE streaming endpoint for the agentic chatbot.

POST /api/chat/stream
  Body: { "message": "...", "history": [{"role":"user","content":"..."},...] }
  Streams SSE events back to the client.

GET /api/chat/health
  Quick liveness check for the chatbot subsystem.
"""

import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.agent import run_agent

logger = logging.getLogger("danone.social.chat")

router = APIRouter()


class ChatMessage(BaseModel):
    role: str     # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@router.post("/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """
    Stream the agent's response as Server-Sent Events.

    SSE event types (JSON payloads on 'data:' lines):
      {"type": "tool_call",   "name": "youcom_search", "args": {...}}
      {"type": "tool_result", "name": "youcom_search", "content": "..."}
      {"type": "token",       "content": "Hello..."}
      {"type": "done"}
      {"type": "error",       "content": "..."}
    """
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]

    return StreamingResponse(
        run_agent(req.message, history=history_dicts),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
def chat_health() -> dict:
    return {"status": "ok", "subsystem": "chatbot"}
