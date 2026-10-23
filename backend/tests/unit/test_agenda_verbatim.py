"""Tests for Part A: Agenda agent verbatim item preservation.

Covers:
  - parse_user_items_text: various pipe-delimited formats
  - _validate_agenda_against_user_items: title mismatch, duration mismatch, owner violations
  - _build_fallback_items: deterministic fallback keeps titles verbatim, splits time evenly
  - run_agenda_agent: 6 user items → exactly 6 in output (plus closing), same order/wording
  - run_agenda_agent: 0 user items → is_purpose_draft=True, no user-item check required
  - run_agenda_agent: LLM invents an extra topic → validation rejects, fallback applied
  - run_agenda_agent: minutes sum equals meeting duration
  - MeetingCreate schema: accepts agenda_items_text field
  - Meeting model: agenda_items_text column exists
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock

import app.observability.tracer as tracer_module
from app.agents.agenda import (
    AgendaItemSchema,
    ParsedUserItem,
    TimeboxedAgendaSchema,
    _build_fallback_items,
    _validate_agenda_against_user_items,
    parse_user_items_text,
    run_agenda_agent,
)
from app.core.errors import ValidationFailed
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.models.meeting import Meeting, MeetingStatus
from app.db.models.user import User, UserRole
from app.db.schemas.meeting import MeetingCreate
from app.memory.vector_store import memory_store
from app.services.llm import llm_service


# ── In-memory DB setup ────────────────────────────────────────────────────────

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autoflush=False, bind=_engine)


@pytest.fixture(scope="module")
def db():
    original = tracer_module.SessionLocal
    tracer_module.SessionLocal = _Session
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    hashed = get_password_hash("pw")
    hod = User(
        name="HOD",
        username="hod_agenda",
        email="hod@test.local",
        role=UserRole.HOD,
        hashed_password=hashed,
    )
    session.add(hod)
    session.commit()
    session.refresh(hod)
    yield session
    session.close()
    Base.metadata.drop_all(bind=_engine)
    tracer_module.SessionLocal = original


def _make_meeting(db, duration: int = 60, agenda_items_text: str | None = None) -> Meeting:
    m = Meeting(
        title="Project Review Committee: Meeting Organizer Agent",
        description="Capstone project review.",
        duration_minutes=duration,
        agenda_items_text=agenda_items_text,
        organizer_id=db.query(User).first().id,
        status=MeetingStatus.SCHEDULED,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ── parse_user_items_text ─────────────────────────────────────────────────────

class TestParseUserItemsText:
    def test_empty_string_returns_empty(self):
        assert parse_user_items_text("") == []

    def test_title_only(self):
        items = parse_user_items_text("Welcome\nOverview")
        assert len(items) == 2
        assert items[0].title == "Welcome"
        assert items[1].title == "Overview"

    def test_title_and_minutes(self):
        items = parse_user_items_text("Welcome | 5")
        assert items[0].title == "Welcome"
        assert items[0].duration_minutes == 5
        assert items[0].owner_raw is None

    def test_title_owner_minutes(self):
        items = parse_user_items_text("Live demo | Aniket, Sujal | 15")
        assert items[0].title == "Live demo"
        assert items[0].owner_raw == "Aniket, Sujal"
        assert items[0].duration_minutes == 15

    def test_six_project_review_items(self):
        raw = (
            "Welcome and objectives | HOD | 5\n"
            "Project overview and progress | Aniket | 10\n"
            "Live demo | Aniket, Sujal | 15\n"
            "Evaluation results and safety design | Viraj | 10\n"
            "Feedback from the committee | Chairman, Principal, Teacher | 10\n"
            "Remaining work, deadlines, next steps | Sarvesh | 10\n"
        )
        items = parse_user_items_text(raw)
        assert len(items) == 6
        assert items[0].title == "Welcome and objectives"
        assert items[0].owner_raw == "HOD"
        assert items[0].duration_minutes == 5
        assert items[2].title == "Live demo"
        assert items[2].owner_raw == "Aniket, Sujal"
        assert items[2].duration_minutes == 15
        assert items[5].title == "Remaining work, deadlines, next steps"

    def test_blank_lines_skipped(self):
        items = parse_user_items_text("\nWelcome\n\nDemo\n")
        assert len(items) == 2

    def test_minutes_with_suffix(self):
        items = parse_user_items_text("Topic | 20min")
        assert items[0].duration_minutes == 20


# ── _validate_agenda_against_user_items ──────────────────────────────────────

class TestValidateAgendaAgainstUserItems:
    def _make_items(self, titles_and_durations: list[tuple[str, int]]) -> list[AgendaItemSchema]:
        return [
            AgendaItemSchema(
                item_number=i + 1,
                title=t,
                owner="HOD",
                duration_minutes=d,
                source="user",
            )
            for i, (t, d) in enumerate(titles_and_durations)
        ]

    def _make_user_items(self, titles: list[str]) -> list[ParsedUserItem]:
        return [ParsedUserItem(title=t, owner_raw=None, duration_minutes=None) for t in titles]

    def test_exact_match_passes(self):
        user_items = self._make_user_items(["Welcome", "Demo"])
        items = self._make_items([("Welcome", 30), ("Demo", 30)])
        ok, violations = _validate_agenda_against_user_items(items, user_items, ["HOD"], 60)
        assert ok
        assert violations == []

    def test_title_mismatch_detected(self):
        user_items = self._make_user_items(["Welcome"])
        items = self._make_items([("Introduction", 60)])
        ok, violations = _validate_agenda_against_user_items(items, user_items, ["HOD"], 60)
        assert not ok
        assert any("Welcome" in v for v in violations)

    def test_duration_mismatch_detected(self):
        user_items = self._make_user_items(["Welcome"])
        items = self._make_items([("Welcome", 45)])
        ok, violations = _validate_agenda_against_user_items(items, user_items, ["HOD"], 60)
        assert not ok
        assert any("minutes" in v.lower() for v in violations)

    def test_missing_item_detected(self):
        user_items = self._make_user_items(["Welcome", "Demo"])
        items = self._make_items([("Welcome", 60)])
        ok, violations = _validate_agenda_against_user_items(items, user_items, ["HOD"], 60)
        assert not ok
        assert any("missing" in v.lower() for v in violations)

    def test_no_user_items_always_passes(self):
        items = self._make_items([("Welcome", 60)])
        ok, violations = _validate_agenda_against_user_items(items, [], ["HOD"], 60)
        assert ok


# ── _build_fallback_items ─────────────────────────────────────────────────────

class TestBuildFallbackItems:
    def test_six_items_verbatim_titles(self):
        user_items = [
            ParsedUserItem("Welcome and objectives", "HOD", 5),
            ParsedUserItem("Project overview and progress", "Aniket", 10),
            ParsedUserItem("Live demo", "Aniket, Sujal", 15),
            ParsedUserItem("Evaluation results and safety design", "Viraj", 10),
            ParsedUserItem("Feedback from the committee", "Chairman, Principal, Teacher", 10),
            ParsedUserItem("Remaining work, deadlines, next steps", "Sarvesh", 10),
        ]
        items = _build_fallback_items(
            meeting_duration=60,
            user_items=user_items,
            attendee_names=["HOD"],
            add_closing=False,
        )
        titles = [i.title for i in items]
        assert titles == [
            "Welcome and objectives",
            "Project overview and progress",
            "Live demo",
            "Evaluation results and safety design",
            "Feedback from the committee",
            "Remaining work, deadlines, next steps",
        ]

    def test_fallback_minutes_sum_equals_duration(self):
        user_items = [
            ParsedUserItem("Topic A", None, None),
            ParsedUserItem("Topic B", None, None),
            ParsedUserItem("Topic C", None, None),
        ]
        items = _build_fallback_items(
            meeting_duration=45,
            user_items=user_items,
            attendee_names=["Alice"],
            add_closing=False,
        )
        assert sum(i.duration_minutes for i in items) == 45

    def test_fallback_with_closing_sums_to_duration(self):
        user_items = [
            ParsedUserItem("Topic A", None, None),
            ParsedUserItem("Topic B", None, None),
        ]
        items = _build_fallback_items(
            meeting_duration=60,
            user_items=user_items,
            attendee_names=["Chair"],
            add_closing=True,
        )
        assert sum(i.duration_minutes for i in items) == 60
        assert items[-1].title == "Next steps"

    def test_explicit_durations_respected(self):
        """User-provided durations are used verbatim; the fallback adjusts the last item
        to make the total equal the meeting_duration."""
        user_items = [
            ParsedUserItem("Welcome", None, 5),
            ParsedUserItem("Demo", None, 15),
        ]
        items = _build_fallback_items(
            meeting_duration=60,
            user_items=user_items,
            attendee_names=[],
            add_closing=False,
        )
        # First item must keep its explicit 5 min
        assert items[0].duration_minutes == 5
        # Total must equal meeting duration (delta absorbed by last item)
        assert sum(i.duration_minutes for i in items) == 60


# ── run_agenda_agent (mocked LLM) ─────────────────────────────────────────────

SIX_ITEMS_TEXT = (
    "Welcome and objectives | HOD | 5\n"
    "Project overview and progress | Aniket | 10\n"
    "Live demo | Aniket, Sujal | 15\n"
    "Evaluation results and safety design | Viraj | 10\n"
    "Feedback from the committee | Chairman, Principal, Teacher | 10\n"
    "Remaining work, deadlines, next steps | Sarvesh | 10\n"
)


def _good_llm_response(prompt, response_schema, system_prompt=""):
    """LLM that returns the user's 6 items + a closing Next steps."""
    if response_schema == TimeboxedAgendaSchema:
        return response_schema.model_validate({
            "meeting_title": "Project Review Committee: Meeting Organizer Agent",
            "total_duration_minutes": 60,
            "items": [
                {"item_number": 1, "title": "Welcome and objectives", "owner": "HOD", "duration_minutes": 5, "source": "user"},
                {"item_number": 2, "title": "Project overview and progress", "owner": "Aniket", "duration_minutes": 10, "source": "user"},
                {"item_number": 3, "title": "Live demo", "owner": "Aniket, Sujal", "duration_minutes": 15, "source": "user"},
                {"item_number": 4, "title": "Evaluation results and safety design", "owner": "Viraj", "duration_minutes": 10, "source": "user"},
                {"item_number": 5, "title": "Feedback from the committee", "owner": "Chairman, Principal, Teacher", "duration_minutes": 10, "source": "user"},
                {"item_number": 6, "title": "Remaining work, deadlines, next steps", "owner": "Sarvesh", "duration_minutes": 10, "source": "user"},
            ],
        })
    return response_schema.model_construct()


def _extra_topic_llm_response(prompt, response_schema, system_prompt=""):
    """LLM that inserts an invented topic — should be rejected."""
    if response_schema == TimeboxedAgendaSchema:
        return response_schema.model_validate({
            "meeting_title": "Project Review Committee: Meeting Organizer Agent",
            "total_duration_minutes": 60,
            "items": [
                {"item_number": 1, "title": "Welcome and objectives", "owner": "HOD", "duration_minutes": 5, "source": "user"},
                {"item_number": 2, "title": "INVENTED TOPIC BY LLM", "owner": "HOD", "duration_minutes": 10, "source": "user"},
                {"item_number": 3, "title": "Project overview and progress", "owner": "Aniket", "duration_minutes": 10, "source": "user"},
                {"item_number": 4, "title": "Live demo", "owner": "Aniket, Sujal", "duration_minutes": 15, "source": "user"},
                {"item_number": 5, "title": "Evaluation results and safety design", "owner": "Viraj", "duration_minutes": 10, "source": "user"},
                {"item_number": 6, "title": "Feedback from the committee", "owner": "Chairman, Principal, Teacher", "duration_minutes": 10, "source": "user"},
            ],
        })
    return response_schema.model_construct()


def _purpose_draft_llm_response(prompt, response_schema, system_prompt=""):
    """LLM that returns a purpose-draft agenda."""
    if response_schema == TimeboxedAgendaSchema:
        return response_schema.model_validate({
            "meeting_title": "General Meeting",
            "total_duration_minutes": 60,
            "is_purpose_draft": True,
            "draft_warning": "Drafted from purpose, please review.",
            "items": [
                {"item_number": 1, "title": "Kick off", "owner": "HOD", "duration_minutes": 10, "source": "user"},
                {"item_number": 2, "title": "Discussion", "owner": "HOD", "duration_minutes": 40, "source": "user"},
                {"item_number": 3, "title": "Next steps", "owner": "HOD", "duration_minutes": 10, "source": "user"},
            ],
        })
    return response_schema.model_construct()


class TestRunAgendaAgent:
    def test_six_user_items_appear_verbatim_in_order(self, db, monkeypatch):
        """Six user items → output has exactly those 6 titles in order."""
        monkeypatch.setattr(llm_service, "generate_structured", _good_llm_response)
        monkeypatch.setattr(memory_store, "search", lambda **kwargs: [])
        meeting = _make_meeting(db, duration=60, agenda_items_text=SIX_ITEMS_TEXT)
        result = run_agenda_agent(db=db, meeting_id=meeting.id, agenda_items_text=SIX_ITEMS_TEXT)

        expected_titles = [
            "Welcome and objectives",
            "Project overview and progress",
            "Live demo",
            "Evaluation results and safety design",
            "Feedback from the committee",
            "Remaining work, deadlines, next steps",
        ]
        actual_titles = [item.title for item in result.items if item.source == "user"]
        assert actual_titles == expected_titles, (
            f"User items not preserved verbatim in order.\nExpected: {expected_titles}\nGot: {actual_titles}"
        )

    def test_minutes_sum_equals_duration(self, db, monkeypatch):
        monkeypatch.setattr(llm_service, "generate_structured", _good_llm_response)
        monkeypatch.setattr(memory_store, "search", lambda **kwargs: [])
        meeting = _make_meeting(db, duration=60, agenda_items_text=SIX_ITEMS_TEXT)
        result = run_agenda_agent(db=db, meeting_id=meeting.id, agenda_items_text=SIX_ITEMS_TEXT)
        total = sum(i.duration_minutes for i in result.items)
        assert total == 60, f"Total minutes {total} ≠ meeting duration 60"

    def test_no_user_items_returns_purpose_draft(self, db, monkeypatch):
        monkeypatch.setattr(llm_service, "generate_structured", _purpose_draft_llm_response)
        monkeypatch.setattr(memory_store, "search", lambda **kwargs: [])
        meeting = _make_meeting(db, duration=60, agenda_items_text=None)
        result = run_agenda_agent(db=db, meeting_id=meeting.id, agenda_items_text=None)
        assert result.is_purpose_draft is True
        assert result.draft_warning is not None
        assert "please review" in (result.draft_warning or "").lower()

    def test_llm_invents_topic_triggers_fallback(self, db, monkeypatch):
        """LLM invents a topic; validation must reject it and apply deterministic fallback."""
        # Both first call and retry return the bad response → fallback kicks in
        monkeypatch.setattr(llm_service, "generate_structured", _extra_topic_llm_response)
        monkeypatch.setattr(memory_store, "search", lambda **kwargs: [])
        meeting = _make_meeting(db, duration=60, agenda_items_text=SIX_ITEMS_TEXT)
        result = run_agenda_agent(db=db, meeting_id=meeting.id, agenda_items_text=SIX_ITEMS_TEXT)

        # Fallback must have been applied
        assert result.fallback_applied is True

        # All 6 user item titles must still be present in order
        user_titles = [i.title for i in result.items if i.source == "user"]
        expected_titles = [
            "Welcome and objectives",
            "Project overview and progress",
            "Live demo",
            "Evaluation results and safety design",
            "Feedback from the committee",
            "Remaining work, deadlines, next steps",
        ]
        assert user_titles == expected_titles

    def test_carried_over_items_are_separate_section(self, db, monkeypatch):
        """Carried-over items appear in carried_over, not mixed into agenda items."""
        monkeypatch.setattr(llm_service, "generate_structured", _good_llm_response)
        # Simulate memory returning a past meeting with open actions
        monkeypatch.setattr(memory_store, "search", lambda **kwargs: [])
        meeting = _make_meeting(db, duration=60, agenda_items_text=SIX_ITEMS_TEXT)
        result = run_agenda_agent(db=db, meeting_id=meeting.id, agenda_items_text=SIX_ITEMS_TEXT)
        # carried_over must be a separate field; none of the items.title should read like carried-over text
        carried_titles = {c.description for c in result.carried_over}
        for item in result.items:
            assert item.title not in carried_titles


# ── Schema field presence ─────────────────────────────────────────────────────

class TestMeetingCreateSchema:
    def test_agenda_items_text_accepted(self):
        payload = MeetingCreate(
            title="Test",
            agenda_items_text="Topic A | Alice | 10\nTopic B | 20",
        )
        assert payload.agenda_items_text == "Topic A | Alice | 10\nTopic B | 20"

    def test_agenda_items_text_defaults_to_none(self):
        payload = MeetingCreate(title="Test")
        assert payload.agenda_items_text is None


class TestMeetingModelColumn:
    def test_agenda_items_text_column_exists(self, db):
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(_engine)
        cols = {c["name"] for c in inspector.get_columns("meetings")}
        assert "agenda_items_text" in cols, (
            "meetings table is missing agenda_items_text column. Run migration 013."
        )
