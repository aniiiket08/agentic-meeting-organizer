from datetime import datetime, timezone
from typing import Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.action_tracker import run_action_tracker_agent
from app.agents.agenda import run_agenda_agent
from app.agents.distribution import run_distribution_agent
from app.agents.minutes import run_minutes_agent
from app.agents.reminder import run_reminder_agent
from app.agents.room_booking import run_room_booking_agent
from app.agents.scheduling import run_scheduling_agent
from app.agents.state import MeetingState
from app.core.errors import ApprovalRequired, NotFound, ToolError, ValidationFailed
from app.db.models.agenda import Agenda, AgendaStatus, Decision
from app.db.models.meeting import Meeting, MeetingStatus
from app.db.models.minutes import Minutes, MinutesStatus, Transcript
from app.db.session import SessionLocal
from app.db.models.user import User
from app.observability.tracer import trace_agent


def _meeting_id(state: MeetingState) -> int:
    meeting_id = state.get("meeting_id")
    if meeting_id is None:
        raise ValidationFailed("meeting_id is required to run the meeting graph.")
    return meeting_id


@trace_agent("scheduling_node")
def schedule_node(state: MeetingState) -> MeetingState:
    """Graph Node: Schedule meeting and select top slot."""
    attendees = state.get("attendees", [])
    slots = run_scheduling_agent(attendee_emails=attendees, meeting_id=_meeting_id(state))
    if not slots:
        raise ToolError("Scheduling returned no candidate slots.", tool_name="scheduling_agent")
    best_slot = slots[0]
    return {"slot": best_slot}


@trace_agent("room_booking_node")
def book_room_node(state: MeetingState) -> MeetingState:
    """Graph Node: Book available room for selected slot."""
    meeting_id = _meeting_id(state)
    slot = state.get("slot")
    attendees = state.get("attendees", [])

    if not slot:
        raise ValidationFailed("Cannot book a room without a selected slot.")

    with SessionLocal() as db:
        res = run_room_booking_agent(
            db=db,
            meeting_id=meeting_id,
            headcount=len(attendees),
            start_time_iso=slot["start_time"],
            end_time_iso=slot["end_time"],
        )
        return {"room": res.get("room")}


@trace_agent("agenda_node")
def agenda_node(state: MeetingState) -> MeetingState:
    """Graph Node: Draft time-boxed agenda using RAG memory."""
    meeting_id = _meeting_id(state)
    with SessionLocal() as db:
        # Fetch agenda_items_text from the meeting so user-supplied items are honoured.
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting is None:
            raise ValidationFailed(f"Meeting {meeting_id} not found.")
        agenda_model = run_agenda_agent(
            db=db,
            meeting_id=meeting_id,
            agenda_items_text=meeting.agenda_items_text or None,
        )
        agenda_dict = agenda_model.model_dump()

        db_agenda = db.query(Agenda).filter(Agenda.meeting_id == meeting_id).first()
        if not db_agenda:
            db_agenda = Agenda(
                meeting_id=meeting_id,
                items_json=agenda_dict["items"],
                status=AgendaStatus.DRAFT,
            )
            db.add(db_agenda)
        else:
            db_agenda.items_json = agenda_dict["items"]
            db_agenda.status = AgendaStatus.DRAFT
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = MeetingStatus.AGENDA_DRAFTED
        db.commit()

        return {"agenda": agenda_dict, "approval_status": "pending"}


def approval_gate_node(state: MeetingState) -> MeetingState:
    """Graph Node: Human Approval Gate pause point for agenda."""
    approval_status = state.get("approval_status")
    if approval_status not in {"approved", "rejected"}:
        raise ApprovalRequired("Agenda approval is required before proceeding.")

    meeting_id = _meeting_id(state)
    with SessionLocal() as db:
        agenda = db.query(Agenda).filter(Agenda.meeting_id == meeting_id).first()
        if agenda is None:
            raise NotFound(entity="Agenda", identifier=meeting_id)
        if approval_status == "approved":
            approver_id = state.get("approved_by_id")
            if approver_id is None or db.query(User.id).filter(User.id == approver_id).first() is None:
                raise ValidationFailed("A valid approver is required to approve the agenda.")
            agenda.status = AgendaStatus.APPROVED
            agenda.approved_by_id = approver_id
            agenda.approved_at = datetime.now(timezone.utc)
        else:
            agenda.status = AgendaStatus.REJECTED
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting and approval_status == "approved":
            meeting.status = MeetingStatus.AGENDA_APPROVED
        db.commit()
    return state


@trace_agent("minutes_node")
def minutes_node(state: MeetingState) -> MeetingState:
    """Graph Node: Extract grounded minutes & action items from transcript."""
    meeting_id = _meeting_id(state)
    transcript_text = state.get("transcript", "")
    if not transcript_text:
        with SessionLocal() as db:
            transcript = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).first()
            if transcript:
                transcript_text = transcript.redacted_text

    if not transcript_text:
        raise ValidationFailed("No transcript is available to generate minutes.")

    minutes_data = run_minutes_agent(transcript_text=transcript_text, meeting_id=meeting_id)

    with SessionLocal() as db:
        db_minutes = (
            db.query(Minutes)
            .filter(Minutes.meeting_id == meeting_id)
            .order_by(Minutes.version.desc())
            .first()
        )
        if db_minutes is None:
            db_minutes = Minutes(
                meeting_id=meeting_id,
                version=1,
                summary=minutes_data["summary"],
                key_discussion_points=minutes_data["key_discussion_points"],
                action_items_json=minutes_data["action_items"],
                status=MinutesStatus.DRAFT,
                content_hash=minutes_data["content_hash"],
            )
            db.add(db_minutes)
        else:
            db_minutes.summary = minutes_data["summary"]
            db_minutes.key_discussion_points = minutes_data["key_discussion_points"]
            db_minutes.action_items_json = minutes_data["action_items"]
            db_minutes.status = MinutesStatus.DRAFT
            db_minutes.content_hash = minutes_data["content_hash"]
        db.query(Decision).filter(Decision.meeting_id == meeting_id).delete()
        db.add_all(
            Decision(
                meeting_id=meeting_id,
                text=item["text"],
                source_quote=item["source_quote"],
                timestamp=item["timestamp"],
            )
            for item in minutes_data["decisions"]
        )
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = MeetingStatus.MINUTES_DRAFTED
        db.commit()
        db.refresh(db_minutes)
        minutes_data["id"] = db_minutes.id

    return {"minutes": minutes_data, "approval_status": "pending_minutes"}


def approve_minutes_gate_node(state: MeetingState) -> MeetingState:
    """Graph Node: Pause for human approval of minutes."""
    approval_status = state.get("approval_status")
    if approval_status not in {"approved_minutes", "rejected_minutes"}:
        raise ApprovalRequired("Minutes approval is required before follow-up actions.")

    meeting_id = _meeting_id(state)
    with SessionLocal() as db:
        minutes = (
            db.query(Minutes)
            .filter(Minutes.meeting_id == meeting_id)
            .order_by(Minutes.version.desc())
            .first()
        )
        if minutes is None:
            raise NotFound(entity="Minutes", identifier=meeting_id)
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if approval_status == "approved_minutes":
            approver_id = state.get("approved_by_id")
            if approver_id is None or db.query(User.id).filter(User.id == approver_id).first() is None:
                raise ValidationFailed("A valid approver is required to approve minutes.")
            minutes.status = MinutesStatus.APPROVED
            minutes.approved_by_id = approver_id
            minutes.approved_at = datetime.now(timezone.utc)
            if meeting:
                meeting.status = MeetingStatus.MINUTES_APPROVED
        else:
            minutes.status = MinutesStatus.REJECTED
        db.commit()
    return state


@trace_agent("actions_node")
def actions_node(state: MeetingState) -> MeetingState:
    """Graph Node: Create tracked action items from approved minutes."""
    meeting_id = _meeting_id(state)

    with SessionLocal() as db:
        minutes = (
            db.query(Minutes)
            .filter(Minutes.meeting_id == meeting_id, Minutes.status == MinutesStatus.APPROVED)
            .order_by(Minutes.version.desc())
            .first()
        )
        if minutes is None:
            raise ApprovalRequired("Action tracking requires approved minutes.")
        actions = run_action_tracker_agent(
            db=db,
            meeting_id=meeting_id,
            extracted_actions=minutes.action_items_json,
        )
        return {"actions": [a.id for a in actions]}


@trace_agent("distribute_node")
def distribute_node(state: MeetingState) -> MeetingState:
    """Graph Node: Distribute approved minutes and calendar items."""
    meeting_id = _meeting_id(state)
    with SessionLocal() as db:
        res = run_distribution_agent(db=db, meeting_id=meeting_id)
        if res.get("status") not in {"distributed", "already_distributed"}:
            raise ToolError("Approved minutes were not distributed.", tool_name="distribution_agent")
        return {"approval_status": res["status"]}


@trace_agent("reminders_node")
def reminders_node(state: MeetingState) -> MeetingState:
    """Graph Node: Process reminder escalation ladder."""
    with SessionLocal() as db:
        res = run_reminder_agent(db=db, meeting_id=_meeting_id(state))
        return {"approval_status": "completed"}


def route_after_agenda_approval(state: MeetingState) -> str:
    status = state.get("approval_status", "pending")
    if status == "approved":
        return "minutes"
    if status == "rejected":
        return "rejected"
    raise ApprovalRequired("Agenda approval is required before proceeding.")


def route_after_minutes_approval(state: MeetingState) -> str:
    status = state.get("approval_status", "pending_minutes")
    if status == "approved_minutes":
        return "actions"
    if status == "rejected_minutes":
        return "rejected"
    raise ApprovalRequired("Minutes approval is required before follow-up actions.")


def build_meeting_graph():
    """Build and compile the complete meeting lifecycle LangGraph state graph."""
    builder = StateGraph(MeetingState)

    builder.add_node("schedule", schedule_node)
    builder.add_node("book_room", book_room_node)
    builder.add_node("agenda", agenda_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("minutes", minutes_node)
    builder.add_node("approve_minutes_gate", approve_minutes_gate_node)
    builder.add_node("actions", actions_node)
    builder.add_node("distribute", distribute_node)
    builder.add_node("reminders", reminders_node)

    builder.set_entry_point("schedule")
    builder.add_edge("schedule", "book_room")
    builder.add_edge("book_room", "agenda")
    builder.add_edge("agenda", "approval_gate")

    builder.add_conditional_edges(
        "approval_gate",
        route_after_agenda_approval,
        {
            "minutes": "minutes",
            "rejected": END,
        },
    )

    builder.add_edge("minutes", "approve_minutes_gate")
    builder.add_conditional_edges(
        "approve_minutes_gate",
        route_after_minutes_approval,
        {
            "actions": "actions",
            "rejected": END,
        },
    )

    builder.add_edge("actions", "distribute")
    builder.add_edge("distribute", "reminders")
    builder.add_edge("reminders", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory, interrupt_before=["approval_gate", "approve_minutes_gate"])


meeting_graph = build_meeting_graph()
