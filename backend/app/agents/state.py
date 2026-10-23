from typing import Any, TypedDict


class MeetingState(TypedDict, total=False):
    meeting_id: int
    attendees: list[str]
    slot: dict[str, Any] | None
    room: dict[str, Any] | None
    agenda: dict[str, Any] | None
    transcript: str | None
    minutes: dict[str, Any] | None
    decisions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    approval_status: str  # "pending", "approved", "rejected"
    approved_by_id: int
    errors: list[str]
    trace_id: str
