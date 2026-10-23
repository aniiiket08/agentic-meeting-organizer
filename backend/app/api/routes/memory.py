from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.models.user import User
from app.memory.vector_store import memory_store

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryQueryRequest(BaseModel):
    query: str


@router.post("/ask")
def query_meeting_memory(
    payload: MemoryQueryRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Cited Memory Chat Q&A across past meeting minutes."""
    results = memory_store.search(query=payload.query, top_k=3)

    citations = [
        {
            "meeting_id": r["meeting_id"],
            "title": r["title"],
            "date": r["date"],
            "snippet": r["text"],
        }
        for r in results
    ]

    answer = f"Based on prior meeting records regarding '{payload.query}', the team decided and documented: '{results[0]['text']}'" if results else "No direct decision found in past meeting records."

    return {
        "question": payload.query,
        "answer": answer,
        "citations": citations,
    }
