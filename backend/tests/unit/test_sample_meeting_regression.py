import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models
import app.observability.tracer as tracer_module
from app.agents.action_tracker import run_action_tracker_agent
from app.agents.minutes import run_minutes_agent
from app.core.pii import redact_pii
from app.db.base import Base
from app.db.models.meeting import Meeting, MeetingStatus
from app.db.models.minutes import Minutes, MinutesStatus, Transcript
from app.db.models.room import Room
from app.db.models.user import User, UserRole


ROOT = Path(__file__).resolve().parents[3]
TRANSCRIPT_PATH = ROOT / "data" / "sample_meeting_transcript.txt"
GOLD_PATH = ROOT / "data" / "sample_meeting_gold.json"
ACTIVE_KEY = (
    __import__("app.config", fromlist=["settings"]).settings.GEMINI_API_KEY
)
HAS_LLM_KEY = bool(ACTIVE_KEY) and not ACTIVE_KEY.startswith("your_")


def _normalized(value: str) -> str:
    return " ".join(value.lower().split())


def _item_text(item) -> str:
    if isinstance(item, str):
        return item
    return str(item.get("text") or item.get("title") or item.get("description") or "")


@pytest.mark.skipif(
    not TRANSCRIPT_PATH.exists() or not GOLD_PATH.exists() or not HAS_LLM_KEY,
    reason="Requires the requested sample transcript, gold JSON, and a configured LLM provider.",
)
def test_sample_meeting_matches_gold_and_acceptance_criteria(monkeypatch):
    transcript_text = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    gold_decisions = gold.get("decisions", gold.get("gold_decisions"))
    gold_actions = gold.get("action_items", gold.get("actions", gold.get("gold_actions")))
    assert isinstance(gold_decisions, list) and isinstance(gold_actions, list), (
        "Gold JSON must contain decisions and action_items/actions lists."
    )

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(autoflush=False, bind=engine)
    monkeypatch.setattr(tracer_module, "SessionLocal", test_session_local)
    db = test_session_local()
    hod = User(
        name="HOD",
        username="hod",
        email="hod@test.local",
        role=UserRole.HOD,
        hashed_password="unused",
    )
    room = Room(name="Regression Room", capacity=10, equipment=[])
    db.add_all([hod, room])
    db.commit()
    meeting = Meeting(
        title="Sample Meeting Regression",
        organizer_id=hod.id,
        room_id=room.id,
        duration_minutes=60,
        status=MeetingStatus.MINUTES_DRAFTED,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    redacted = redact_pii(transcript_text)
    db.add(
        Transcript(
            meeting_id=meeting.id,
            raw_text=transcript_text,
            redacted_text=redacted,
            content_hash="sample-regression-transcript",
        )
    )
    db.commit()

    minutes = run_minutes_agent(redacted, meeting_id=meeting.id)
    actual_decisions = [item["text"] for item in minutes["decisions"]]
    actual_actions = minutes["action_items"]
    actual_action_texts = [item["title"] for item in actual_actions]
    expected_decisions = [_item_text(item) for item in gold_decisions]
    expected_actions = [_item_text(item) for item in gold_actions]
    missed_decisions = [
        expected
        for expected in expected_decisions
        if not any(_normalized(expected) in _normalized(actual) for actual in actual_decisions)
    ]
    missed_actions = [
        expected
        for expected in expected_actions
        if not any(_normalized(expected) in _normalized(actual) for actual in actual_action_texts)
    ]
    extra_actions = [
        actual
        for actual in actual_action_texts
        if not any(_normalized(expected) in _normalized(actual) for expected in expected_actions)
    ]
    extra_decisions = [
        actual
        for actual in actual_decisions
        if not any(_normalized(expected) in _normalized(actual) for expected in expected_decisions)
    ]
    assert len(actual_decisions) == 3, f"Expected 3 decisions; got {actual_decisions}"
    assert len(actual_actions) == 6, f"Expected 6 grounded actions; got {actual_action_texts}"
    assert not missed_decisions, f"Gold decisions missed: {missed_decisions}"
    assert not missed_actions, f"Gold actions missed: {missed_actions}"
    assert not extra_decisions, f"Extra decisions not in gold: {extra_decisions}"
    assert not extra_actions, f"Extra actions not in gold: {extra_actions}"
    assert not any("mobile app" in item.lower() for item in actual_action_texts)
    for item in actual_actions:
        assert item["source_quote"] and item["timestamp"]
        assert any(
            item["source_quote"] in line and item["timestamp"] in line
            for line in redacted.splitlines()
        ), f"Action lacks same-line timestamped evidence: {item['title']}"

    projector = next(item for item in actual_actions if "projector" in item["title"].lower())
    assert projector["owner_email"] is None
    approved = Minutes(
        meeting_id=meeting.id,
        version=1,
        summary=minutes["summary"],
        key_discussion_points=minutes["key_discussion_points"],
        action_items_json=actual_actions,
        status=MinutesStatus.APPROVED,
        content_hash=minutes["content_hash"],
            approved_by_id=hod.id,
    )
    db.add(approved)
    db.commit()
    tracked = run_action_tracker_agent(db, meeting.id, actual_actions)
    projector_task = next(item for item in tracked if "projector" in item.description.lower())
    assert projector_task.owner_id is None
    assert projector_task.needs_confirmation is True

    arjun_action = next(
        item
        for item in actual_actions
        if "arjun" in (item.get("owner_email") or "").lower()
        or "arjun" in item["title"].lower()
    )
    assert arjun_action["due_date"] == "2026-10-09"
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()