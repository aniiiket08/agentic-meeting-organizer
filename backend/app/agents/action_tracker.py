import logging
from datetime import date, datetime, timezone
from typing import Any
from pydantic import BaseModel, EmailStr, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import ApprovalRequired, ToolError, ValidationFailed
from app.db.models.action import ActionItem, ActionStatus, ActionPriority
from app.db.models.minutes import Minutes
from app.db.models.minutes import MinutesStatus, Transcript
from app.db.models.user import User
from app.observability.tracer import record_tool_call, trace_agent
from app.services.grounding import grounding_checker

logger = logging.getLogger("meeting_organizer")


class ApprovedActionSchema(BaseModel):
    title: str = Field(min_length=1)
    owner_email: EmailStr | None = None
    owner_name: str | None = None
    due_date: date | None = None
    priority: ActionPriority
    source_quote: str = Field(min_length=1)
    timestamp: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}:\d{2}$")


def prepare_draft_action_items(
    db: Session,
    meeting_id: int,
    extracted_actions: list[dict[str, Any]],
) -> list[ActionItem]:
    """Build new draft action records from validated, transcript-grounded candidates."""
    minutes = (
        db.query(Minutes)
        .filter(Minutes.meeting_id == meeting_id, Minutes.status == MinutesStatus.DRAFT)
        .order_by(Minutes.version.desc())
        .first()
    )
    if minutes is None or extracted_actions != minutes.action_items_json:
        raise ValidationFailed("Draft action candidates do not match the saved minutes.")

    transcript = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).first()
    if transcript is None:
        raise ValidationFailed("Cannot ground action items without the meeting transcript.")

    try:
        validated_actions = [
            ApprovedActionSchema.model_validate(item).model_dump(mode="json")
            for item in extracted_actions
        ]
    except ValidationError as exc:
        logger.exception("Draft action candidates failed schema validation")
        raise ValidationFailed("An extracted action candidate is incomplete.") from exc

    valid_actions, dropped_actions = grounding_checker.verify_grounding(
        transcript.redacted_text,
        validated_actions,
    )
    if dropped_actions:
        logger.warning("Draft action persistence dropped %d ungrounded candidates.", len(dropped_actions))

    existing = db.query(ActionItem).filter(ActionItem.meeting_id == meeting_id).all()
    existing_keys = {(item.description, item.source_quote) for item in existing}
    created_items = []

    for item in valid_actions:
        signature = (item["title"], item["source_quote"])
        if signature in existing_keys:
            continue

        owner = None
        if item.get("owner_email"):
            owner = (
                db.query(User)
                .filter(func.lower(User.email) == item["owner_email"].lower())
                .first()
            )
        if owner is None and item.get("owner_name"):
            owner = (
                db.query(User)
                .filter(func.lower(User.name) == item["owner_name"].strip().lower())
                .first()
            )

        due_date_value = item.get("due_date")
        due_date = (
            datetime.combine(date.fromisoformat(due_date_value), datetime.min.time(), tzinfo=timezone.utc)
            if due_date_value
            else None
        )
        action = ActionItem(
            meeting_id=meeting_id,
            description=item["title"],
            owner_id=owner.id if owner else None,
            owner_name=owner.name if owner else item.get("owner_name"),
            owner_email=owner.email if owner else item.get("owner_email"),
            due_date=due_date,
            priority=item["priority"],
            status=ActionStatus.PENDING,
            confidence=1.0,
            source_quote=item["source_quote"],
            source_timestamp=item.get("timestamp"),
            needs_confirmation=owner is None,
        )
        db.add(action)
        created_items.append(action)
        existing_keys.add(signature)

    return created_items

@trace_agent(agent_name="action_tracker_agent")
def run_action_tracker_agent(
    db: Session,
    meeting_id: int,
    extracted_actions: list[dict[str, Any]],
) -> list[ActionItem]:
    """
    Action Tracker Agent:
    Transforms extracted, grounded action items into persistent ActionItem records in DB.
    Matches owner email to User account, assigns priority, due date, confidence score.
    """
    approved_minutes = (
        db.query(Minutes)
        .filter(Minutes.meeting_id == meeting_id, Minutes.status == MinutesStatus.APPROVED)
        .order_by(Minutes.version.desc())
        .first()
    )
    if approved_minutes is None:
        raise ApprovalRequired("Action items cannot be created before minutes approval.")
    if extracted_actions != approved_minutes.action_items_json:
        raise ValidationFailed("Action candidates do not match the approved minutes version.")

    transcript = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).first()
    if transcript is None:
        raise ValidationFailed("Cannot ground action items without the meeting transcript.")

    if not extracted_actions:
        return []

    try:
        validated_actions = [
            ApprovedActionSchema.model_validate(item).model_dump(mode="json")
            for item in extracted_actions
        ]
    except ValidationError as exc:
        logger.exception("Approved action candidates failed schema validation")
        raise ValidationFailed("An approved action candidate is incomplete.") from exc

    valid_actions, dropped_actions = grounding_checker.verify_grounding(
        transcript.redacted_text,
        validated_actions,
    )
    if dropped_actions:
        logger.warning("Action Tracker dropped %d ungrounded candidates.", len(dropped_actions))
    record_tool_call(
        "grounding_checker.verify_grounding",
        {"candidate_count": len(validated_actions)},
        {"grounded_count": len(valid_actions), "dropped_count": len(dropped_actions)},
    )

    existing_items = db.query(ActionItem).filter(ActionItem.meeting_id == meeting_id).all()
    if existing_items:
        return existing_items

    created_items = []

    for item in valid_actions:
        owner = (
            db.query(User).filter(func.lower(User.email) == item["owner_email"].lower()).first()
            if item["owner_email"]
            else None
        )
        if owner is None and item.get("owner_name"):
            owner = (
                db.query(User)
                .filter(func.lower(User.name) == item["owner_name"].strip().lower())
                .first()
            )
        due_date_val = (
            datetime.combine(date.fromisoformat(item["due_date"]), datetime.min.time(), tzinfo=timezone.utc)
            if item["due_date"]
            else None
        )

        action_rec = ActionItem(
            meeting_id=meeting_id,
            description=item["title"],
            owner_id=owner.id if owner else None,
            owner_name=owner.name if owner else item.get("owner_name"),
            owner_email=owner.email if owner else item.get("owner_email"),
            due_date=due_date_val,
            priority=item["priority"],
            status=ActionStatus.PENDING,
            confidence=1.0,
            source_quote=item["source_quote"],
            source_timestamp=item.get("timestamp"),
            needs_confirmation=owner is None,
        )
        db.add(action_rec)
        created_items.append(action_rec)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist approved action items")
        raise ToolError("Could not save approved action items.", tool_name="database.action_items") from exc
    record_tool_call(
        "database.action_items.insert",
        {"meeting_id": meeting_id},
        {"created_count": len(created_items)},
    )
    for rec in created_items:
        db.refresh(rec)

    return created_items
