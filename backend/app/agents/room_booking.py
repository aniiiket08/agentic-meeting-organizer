from datetime import datetime
from typing import Any
from dateutil.parser import parse as parse_date
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ToolError, ValidationFailed
from app.core.logging import logger
from app.db.models.room import Room
from app.observability.tracer import record_tool_call, trace_agent
from app.services.room_service import room_service


@trace_agent(agent_name="room_booking_agent")
def run_room_booking_agent(
    db: Session,
    meeting_id: int,
    headcount: int,
    start_time_iso: str,
    end_time_iso: str,
    equipment_needed: list[str] | None = None,
    room_id: int | None = None,
) -> dict[str, Any]:
    """Standalone Room Booking Agent function.

    When *room_id* is provided the agent books that specific room after
    verifying it is available for the window.  When *room_id* is None the
    agent finds the best-fit room (smallest capacity that still fits
    headcount and equipment) and books it.

    Raises
    ------
    ValidationFailed  – bad time window
    NotFound          – requested room_id does not exist
    Conflict          – room already booked, or no room fits
    ToolError         – unexpected service failure
    """
    try:
        start_dt = parse_date(start_time_iso)
        end_dt = parse_date(end_time_iso)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationFailed("Room booking window is invalid.") from exc
    if end_dt <= start_dt:
        raise ValidationFailed("Room booking end time must be after its start time.")

    # ── Path A: explicit room chosen by the user ──────────────────────────
    if room_id is not None:
        requested_room = db.query(Room).filter(Room.id == room_id).first()
        if requested_room is None:
            raise NotFound(entity="Room", identifier=room_id)

        # Capacity check
        if requested_room.capacity < headcount:
            raise Conflict(
                f"Room '{requested_room.name}' seats {requested_room.capacity} "
                f"but the meeting has {headcount} attendees.",
                action="choose_another_room",
            )

        # Equipment check
        required_eq = set(equipment_needed or [])
        room_eq = set(requested_room.equipment or [])
        missing = required_eq - room_eq
        if missing:
            raise Conflict(
                f"Room '{requested_room.name}' is missing equipment: {', '.join(sorted(missing))}.",
                action="choose_another_room",
            )

        record_tool_call(
            "room_booking_agent.explicit_room",
            {"room_id": room_id, "headcount": headcount, "equipment": list(required_eq)},
            {"room_name": requested_room.name},
        )

        try:
            booked_room = room_service.book_room(
                db=db,
                meeting_id=meeting_id,
                room_id=requested_room.id,
                start_time=start_dt,
                end_time=end_dt,
            )
        except (Conflict, ValidationFailed):
            raise
        except Exception as exc:
            logger.exception("Room booking failed")
            raise ToolError(
                "Could not book the selected room.", tool_name="room_service.book_room"
            ) from exc

        record_tool_call(
            "room_service.book_room",
            {"meeting_id": meeting_id, "room_id": booked_room.id},
            {"room_id": booked_room.id, "status": "booked"},
        )
        return {
            "status": "booked",
            "message": f"Room '{booked_room.name}' successfully booked.",
            "room": {
                "id": booked_room.id,
                "name": booked_room.name,
                "capacity": booked_room.capacity,
                "equipment": booked_room.equipment,
            },
        }

    # ── Path B: auto best-fit ─────────────────────────────────────────────
    try:
        available_rooms = room_service.find_available_rooms(
            db=db,
            capacity_needed=headcount,
            start_time=start_dt,
            end_time=end_dt,
            required_equipment=equipment_needed,
        )
        record_tool_call(
            "room_service.find_available_rooms",
            {"headcount": headcount, "equipment": equipment_needed or []},
            {"room_ids": [room.id for room in available_rooms]},
        )
    except Exception as exc:
        logger.exception("Room availability lookup failed")
        raise ToolError(
            "Could not check room availability.",
            tool_name="room_service.find_available_rooms",
        ) from exc

    if not available_rooms:
        raise Conflict(
            f"No available room matches headcount ({headcount}) and equipment requirements.",
            action="choose_another_room_or_time",
        )

    # Select room with capacity closest to (but not below) headcount
    selected_room = min(available_rooms, key=lambda r: r.capacity)
    try:
        booked_room = room_service.book_room(
            db=db,
            meeting_id=meeting_id,
            room_id=selected_room.id,
            start_time=start_dt,
            end_time=end_dt,
        )
        record_tool_call(
            "room_service.book_room",
            {"meeting_id": meeting_id, "room_id": selected_room.id},
            {"room_id": booked_room.id, "status": "booked"},
        )
    except (Conflict, ValidationFailed):
        raise
    except Exception as exc:
        logger.exception("Room booking failed")
        raise ToolError(
            "Could not book the selected room.", tool_name="room_service.book_room"
        ) from exc

    return {
        "status": "booked",
        "message": f"Room '{booked_room.name}' successfully booked.",
        "room": {
            "id": booked_room.id,
            "name": booked_room.name,
            "capacity": booked_room.capacity,
            "equipment": booked_room.equipment,
        },
    }
