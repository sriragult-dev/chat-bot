"""Request and response models for the API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's question.")
    session_id: Optional[str] = Field(
        default=None,
        description="Omit on the first message; reuse the returned id to keep context.",
    )


class ChatResponse(BaseModel):
    session_id: str
    reply: str


class Turn(BaseModel):
    role: str
    text: str


class HistoryResponse(BaseModel):
    session_id: str
    turns: List[Turn]


class HealthResponse(BaseModel):
    status: str
    model: str
    active_sessions: int
