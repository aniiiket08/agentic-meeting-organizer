from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from dateutil.parser import parse as parse_date

from app.core.errors import ToolError, ValidationFailed
from app.core.logging import logger

MOCK_CALENDAR_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "mock_calendar.json"


class CalendarService:
    """Service to interact with attendee calendars (Mock JSON implementation first)."""

    def __init__(self, data_path: Path = MOCK_CALENDAR_PATH):
        self.data_path = data_path

    def _load_mock_data(self) -> dict[str, list[dict[str, Any]]]:
        if not self.data_path.exists():
            raise ToolError(
                "Configured calendar data file is missing.",
                tool_name="calendar.load_busy_slots",
                details={"path": str(self.data_path)},
            )
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.exception("Could not read configured calendar data")
            raise ToolError("Could not read calendar availability.", tool_name="calendar.load_busy_slots") from exc
        if not isinstance(data, dict):
            raise ValidationFailed("Calendar data must be a mapping of attendee emails to events.")
        return data

    def get_busy_slots(self, emails: list[str]) -> dict[str, list[dict[str, datetime]]]:
        """Fetch busy events for each email address."""
        if not emails:
            raise ValidationFailed("At least one attendee email is required for scheduling.")
        raw_data = self._load_mock_data()
        result: dict[str, list[dict[str, datetime]]] = {}

        for email in emails:
            if email not in raw_data:
                continue
            events = raw_data[email]
            busy_list = []
            try:
                for ev in events:
                    start_dt = parse_date(ev["start"])
                    end_dt = parse_date(ev["end"])
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    if end_dt <= start_dt:
                        raise ValueError("Calendar event end must be after its start.")
                    busy_list.append({"start": start_dt, "end": end_dt, "title": ev.get("title", "Busy")})
            except Exception as exc:
                logger.exception("Invalid calendar event for attendee %s", email)
                raise ToolError(
                    "Calendar availability contains an invalid event.",
                    tool_name="calendar.load_busy_slots",
                    details={"attendee": email},
                ) from exc
            result[email] = busy_list

        return result


calendar_service = CalendarService()
