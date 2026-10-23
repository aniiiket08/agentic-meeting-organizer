from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.db.models.trace import AgentRun
from app.db.models.user import User, UserRole

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("")
def list_agent_traces(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.CHAIRMAN, UserRole.PRINCIPAL, UserRole.HOD)),
) -> list[dict[str, Any]]:
    """List agent execution traces."""
    runs = db.query(AgentRun).order_by(AgentRun.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "meeting_id": r.meeting_id,
            "agent": r.agent,
            "input_data": r.input_data,
            "output_data": r.output_data,
            "latency_ms": r.latency_ms,
            "tokens": r.tokens,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in runs
    ]
