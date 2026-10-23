from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.meeting import Meeting, MeetingStatus
from app.db.models.room import Room
from app.db.models.user import User

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("")
def list_rooms(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """List all available rooms."""
    rooms = db.query(Room).all()
    return [
        {"id": r.id, "name": r.name, "capacity": r.capacity, "equipment": r.equipment}
        for r in rooms
    ]


def _best_fit_reason(room: Room, headcount: int, required_equipment: list[str]) -> str:
    """One-line human explanation for why this room is the best fit."""
    eq_parts = []
    if required_equipment:
        eq_parts.append(", ".join(required_equipment))
    reason = f"Smallest room that seats {headcount}"
    if eq_parts:
        reason += f" with {eq_parts[0]}"
    return reason


@router.get("/availability")
def get_room_availability(
    start_time: str = Query(..., description="ISO-8601 start datetime"),
    end_time: str = Query(..., description="ISO-8601 end datetime"),
    headcount: int = Query(default=1, ge=1),
    equipment: str = Query(default="", description="Comma-separated list of required equipment"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return every room annotated with availability status for the given slot.

    Each room entry contains:
      - id, name, capacity, equipment
      - status: "available" | "booked" | "too_small"
      - reason: why it cannot be selected (empty string when available)
      - is_best_fit: true for the pre-selected recommendation

    Best fit = smallest available room that fits headcount + equipment.
    """
    try:
        # Fix URL-decoded timezones: space became + during URL parsing
        start_time_fixed = start_time.replace(" ", "+") if " " in start_time else start_time
        end_time_fixed = end_time.replace(" ", "+") if " " in end_time else end_time
        start_dt = datetime.fromisoformat(start_time_fixed.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time_fixed.replace("Z", "+00:00"))
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {e}")

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    required_eq = [e.strip() for e in equipment.split(",") if e.strip()] if equipment else []

    all_rooms = db.query(Room).order_by(Room.capacity.asc()).all()

    def is_booked(room: Room) -> bool:
        return (
            db.query(Meeting)
            .filter(
                Meeting.room_id == room.id,
                Meeting.status.notin_([MeetingStatus.CLOSED, MeetingStatus.DISCARDED]),
                Meeting.start_time < end_dt,
                Meeting.end_time > start_dt,
            )
            .first()
            is not None
        )

    annotated: list[dict[str, Any]] = []
    best_fit_id: int | None = None
    best_fit_candidates: list[Room] = []

    for room in all_rooms:
        if room.capacity < headcount:
            annotated.append({
                "id": room.id,
                "name": room.name,
                "capacity": room.capacity,
                "equipment": room.equipment,
                "status": "too_small",
                "reason": f"Seats {room.capacity}, need {headcount}",
                "is_best_fit": False,
            })
            continue

        room_eq = set(room.equipment or [])
        missing = [e for e in required_eq if e not in room_eq]
        if missing:
            annotated.append({
                "id": room.id,
                "name": room.name,
                "capacity": room.capacity,
                "equipment": room.equipment,
                "status": "too_small",   # reuse too_small for missing equipment (not selectable)
                "reason": f"Missing equipment: {', '.join(missing)}",
                "is_best_fit": False,
            })
            continue

        if is_booked(room):
            annotated.append({
                "id": room.id,
                "name": room.name,
                "capacity": room.capacity,
                "equipment": room.equipment,
                "status": "booked",
                "reason": "Already booked for this time",
                "is_best_fit": False,
            })
            continue

        # Room passes all checks — available
        best_fit_candidates.append(room)
        annotated.append({
            "id": room.id,
            "name": room.name,
            "capacity": room.capacity,
            "equipment": room.equipment,
            "status": "available",
            "reason": "",
            "is_best_fit": False,
        })

    # Pre-select the best fit: smallest available room that fits
    if best_fit_candidates:
        best = min(best_fit_candidates, key=lambda r: r.capacity)
        best_fit_id = best.id
        best_fit_reason = _best_fit_reason(best, headcount, required_eq)
        for entry in annotated:
            if entry["id"] == best_fit_id:
                entry["is_best_fit"] = True
                entry["best_fit_reason"] = best_fit_reason
                break

    return {
        "rooms": annotated,
        "best_fit_id": best_fit_id,
        "headcount": headcount,
        "required_equipment": required_eq,
    }
