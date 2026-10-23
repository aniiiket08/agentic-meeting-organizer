import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.models.user import User, UserRole
from app.db.models.meeting import Meeting, MeetingStatus
from app.db.models.minutes import Minutes, MinutesStatus, Transcript
from app.core.security import get_password_hash
import app.observability.tracer as tracer_module

from app.agents.action_tracker import run_action_tracker_agent
from app.agents.reminder import run_reminder_agent
from app.agents.distribution import run_distribution_agent
from app.core.errors import ToolError
from app.services.email_service import email_service

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def test_db():
    original_tracer_session = tracer_module.SessionLocal
    tracer_module.SessionLocal = TestingSessionLocal
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    hashed = get_password_hash("password123")

    users = [
        User(name="HOD", username="hod", email="hod@university.com", role=UserRole.HOD, hashed_password=hashed),
    ]
    db.add_all(users)
    db.commit()
    db.add(
        Meeting(
            title="Phase 5 Test Meeting",
            duration_minutes=60,
            organizer_id=users[0].id,
            status=MeetingStatus.SCHEDULED,
        )
    )
    db.commit()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        tracer_module.SessionLocal = original_tracer_session

def test_action_tracker_agent(test_db):
    extracted = [
        {
            "title": "Review GPU cluster budget",
            "owner_email": "hod@university.com",
            "due_date": "2026-10-10",
            "priority": "high",
            "source_quote": "Review GPU cluster budget",
            "timestamp": "00:00:06",
        }
    ]
    meeting = test_db.query(Meeting).filter_by(id=1).one()
    hod = test_db.query(User).filter_by(email="hod@university.com").one()
    test_db.add(
        Transcript(
            meeting_id=meeting.id,
            raw_text="[00:00:06] Review GPU cluster budget",
            redacted_text="[00:00:06] Review GPU cluster budget",
            content_hash="phase5-transcript",
        )
    )
    test_db.add(
        Minutes(
            meeting_id=meeting.id,
            version=1,
            summary="Approved summary",
            key_discussion_points=[],
            action_items_json=extracted,
            status=MinutesStatus.APPROVED,
            content_hash="phase5-minutes",
            approved_by_id=hod.id,
        )
    )
    test_db.commit()
    actions = run_action_tracker_agent(test_db, meeting_id=1, extracted_actions=extracted)
    assert len(actions) == 1
    assert actions[0].description == "Review GPU cluster budget"

def test_reminder_agent_idempotency(test_db, monkeypatch):
    monkeypatch.setattr(email_service, "send_email", lambda *args, **kwargs: True)
    res1 = run_reminder_agent(test_db)
    res2 = run_reminder_agent(test_db)
    # Second run should send 0 new reminders due to idempotency check
    assert res2["reminders_sent"] == 0

def test_distribution_agent_audit(test_db):
    with pytest.raises(ToolError, match="Email delivery is not configured"):
        email_service.send_email(
            to_email="hod@university.com",
            subject="test",
            body="test",
            idempotency_key="phase5-test",
        )
