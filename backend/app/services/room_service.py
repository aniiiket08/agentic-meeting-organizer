from datetime import datetime
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.db.models.meeting import Meeting, MeetingStatus
from app.db.models.room import Room


class RoomService:
    """Service for searching room availability and double-booking conflict prevention."""

    def find_available_rooms(
        self,
        db: Session,
        capacity_needed: int,
        start_time: datetime,
        end_time: datetime,
        required_equipment: list[str] | None = None,
    ) -> list[Room]:
        """Find rooms matching capacity and equipment requirements that are free during the window."""
        required_eq = set(required_equipment or [])
        all_rooms = db.query(Room).all()
        suitable_rooms: list[Room] = []

        for room in all_rooms:
            # 1. Capacity check
            if room.capacity < capacity_needed:
                continue

            # 2. Equipment check
            room_eq = set(room.equipment or [])
            if not required_eq.issubset(room_eq):
                continue

            # 3. Conflict check against booked meetings
            has_conflict = (
                db.query(Meeting)
                .filter(
                    Meeting.room_id == room.id,
                    Meeting.status.notin_([MeetingStatus.CLOSED, MeetingStatus.DISCARDED]),
                    Meeting.start_time < end_time,
                    Meeting.end_time > start_time,
                )
                .first()
                is not None
            )

            if not has_conflict:
                suitable_rooms.append(room)

        return suitable_rooms

    def book_room(
        self,
        db: Session,
        meeting_id: int,
        room_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Room:
        """Book a room for a meeting with strict double-booking conflict checks."""
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise NotFound(entity="Room", identifier=room_id)

        # Check existing booking conflict
        conflicting_meeting = (
            db.query(Meeting)
            .filter(
                Meeting.room_id == room.id,
                Meeting.id != meeting_id,
                Meeting.status.notin_([MeetingStatus.CLOSED, MeetingStatus.DISCARDED]),
                Meeting.start_time < end_time,
                Meeting.end_time > start_time,
            )
            .first()
        )

        if conflicting_meeting:
            raise Conflict(
                message=f"Room '{room.name}' is already booked between {start_time.strftime('%H:%M')} and {end_time.strftime('%H:%M')}.",
                action="choose_another_room",
            )

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise NotFound(entity="Meeting", identifier=meeting_id)

        meeting.room_id = room.id
        meeting.start_time = start_time
        meeting.end_time = end_time
        meeting.status = MeetingStatus.ROOM_BOOKED
        db.commit()
        db.refresh(meeting)
        return room


room_service = RoomService()
