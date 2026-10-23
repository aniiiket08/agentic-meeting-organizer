from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, visible_meetings_query
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.services.calendar_service import calendar_service

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _iso_date_from_iso(value: str) -> str:
    return value[:10]


def _format_dt_for_display(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%H:%M")


def _combine_schedules(
    user_email: str,
    start_date: datetime,
    end_date: datetime,
    meetings: list[Meeting],
    busy_map: dict[str, list[dict]],
) -> dict:
    """Build a day-keyed schedule with busy blocks from calendar + confirmed meetings."""
    day_map: dict[str, list[dict]] = {}
    current = start_date
    while current < end_date:
        day_map[current.strftime("%Y-%m-%d")] = []
        current += timedelta(days=1)

    for ev in busy_map.get(user_email, []):
        ev_start: datetime = ev["start"]
        ev_end: datetime = ev["end"]
        day_key = ev_start.astimezone(timezone.utc).strftime("%Y-%m-%d")
        if day_key not in day_map:
            continue
        if ev_end < start_date or ev_start > end_date:
            continue
        day_map[day_key].append({
            "type": "busy",
            "start_time": ev_start.isoformat(),
            "end_time": ev_end.isoformat(),
            "start_label": _format_dt_for_display(ev_start),
            "end_label": _format_dt_for_display(ev_end),
            "title": ev.get("title", "Busy"),
            "source": "calendar",
        })

    for meeting in meetings:
        if not meeting.start_time or not meeting.end_time:
            continue
        day_key = meeting.start_time.astimezone(timezone.utc).strftime("%Y-%m-%d")
        if day_key not in day_map:
            continue
        day_map[day_key].append({
            "type": "meeting",
            "start_time": meeting.start_time.isoformat(),
            "end_time": meeting.end_time.isoformat(),
            "start_label": _format_dt_for_display(meeting.start_time),
            "end_label": _format_dt_for_display(meeting.end_time),
            "title": meeting.title,
            "meeting_id": meeting.id,
            "source": "meeting",
        })

    for day_key in day_map:
        day_map[day_key].sort(key=lambda b: b["start_time"])

    return day_map


@router.get("")
def get_my_schedule(
    view: str = Query(default="today", pattern="^(today|week)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the current user's schedule combining busy calendar events and confirmed meetings."""
    now = datetime.now(timezone.utc)
    if view == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
    else:
        weekday = now.weekday()
        start_date = (now - timedelta(days=weekday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date = start_date + timedelta(days=7)

    user_meetings = (
        visible_meetings_query(db, current_user)
        .filter(Meeting.start_time.isnot(None))
        .filter(Meeting.end_time.isnot(None))
        .filter(Meeting.start_time >= start_date)
        .filter(Meeting.start_time < end_date)
        .order_by(Meeting.start_time.asc())
        .all()
    )

    upcoming_meetings = (
        visible_meetings_query(db, current_user)
        .filter(Meeting.start_time.isnot(None))
        .filter(Meeting.start_time >= now)
        .order_by(Meeting.start_time.asc())
        .limit(10)
        .all()
    )

    busy_map = calendar_service.get_busy_slots([current_user.email])

    days = _combine_schedules(
        user_email=current_user.email,
        start_date=start_date,
        end_date=end_date,
        meetings=user_meetings,
        busy_map=busy_map,
    )

    upcoming = []
    for m in upcoming_meetings:
        dt = m.start_time.astimezone(timezone.utc)
        upcoming.append({
            "id": m.id,
            "title": m.title,
            "date_label": dt.strftime("%d %b"),
            "time_label": dt.strftime("%H:%M") + "–" + m.end_time.astimezone(timezone.utc).strftime("%H:%M"),
            "start_time": m.start_time.isoformat(),
            "end_time": m.end_time.isoformat() if m.end_time else None,
        })

    return {
        "view": view,
        "start_date": start_date.date().isoformat(),
        "end_date": (end_date - timedelta(days=1)).date().isoformat(),
        "today": now.date().isoformat(),
        "days": days,
        "working_hours": {
            "start": "09:00",
            "end": "17:00",
        },
        "upcoming_meetings": upcoming,
    }
