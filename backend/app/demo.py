import sys
from app.core.errors import NotFound, ValidationFailed
from app.db.models.meeting import Meeting
from app.db.session import SessionLocal
from app.db.seed import seed_database
from app.agents.graph import meeting_graph

def run_demo(meeting_id: int) -> None:
    """Run a real meeting to the first human approval checkpoint."""
    with SessionLocal() as db:
        seed_database(db)
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting is None:
            raise NotFound(entity="Meeting", identifier=meeting_id)
        attendees = [
            attendee.user.email if attendee.user else attendee.external_email
            for attendee in meeting.attendees
            if attendee.user or attendee.external_email
        ]
        if not attendees:
            raise ValidationFailed("The selected meeting has no registered attendees.")

    print(f"Starting workflow for meeting {meeting_id}.")
    config = {"configurable": {"thread_id": f"meeting-{meeting_id}"}}
    initial_state = {
        "meeting_id": meeting_id,
        "attendees": attendees,
        "approval_status": "pending",
    }

    state = meeting_graph.invoke(initial_state, config)
    print(
        "Workflow paused for human agenda approval: "
        f"slot={state.get('slot', {}).get('start_time')}, "
        f"room={state.get('room', {}).get('name')}"
    )

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.demo <meeting_id>")
    run_demo(int(sys.argv[1]))
