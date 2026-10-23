from datetime import datetime, timezone
import pytest

from app.services.slot_scorer import AttendeeSchedule, SlotCandidate, score_slot_candidates


@pytest.fixture
def base_time():
    return datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)


def test_perfect_slot_scoring(base_time):
    candidates = [SlotCandidate(start_time=base_time, end_time=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc))]
    schedules = [
        AttendeeSchedule(email="user1@test.com", busy_slots=[]),
        AttendeeSchedule(email="user2@test.com", busy_slots=[]),
    ]
    results = score_slot_candidates(candidates, schedules)
    assert len(results) == 1
    assert results[0].score == 100.0
    assert "all 2 free" in results[0].reason
    assert "no back-to-back" in results[0].reason


def test_unknown_calendar_is_not_reported_as_free(base_time):
    candidate = SlotCandidate(
        start_time=base_time,
        end_time=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc),
    )
    schedules = [
        AttendeeSchedule(email="member@test.com", busy_slots=[]),
        AttendeeSchedule(email="guest@gmail.com", availability_known=False),
    ]

    result = score_slot_candidates([candidate], schedules)[0]

    assert "1 of 1 calendars checked free" in result.reason
    assert "1 availability unverified" in result.reason
    assert "all 2 free" not in result.reason


def test_conflict_penalty_regular_attendee(base_time):
    candidates = [SlotCandidate(start_time=base_time, end_time=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc))]
    schedules = [
        AttendeeSchedule(email="user1@test.com", busy_slots=[{"start": base_time, "end": datetime(2026, 10, 5, 10, 30, tzinfo=timezone.utc)}]),
        AttendeeSchedule(email="user2@test.com", busy_slots=[]),
    ]
    results = score_slot_candidates(candidates, schedules)
    assert results[0].score == 70.0
    assert "user1@test.com" in results[0].conflicts


def test_conflict_penalty_priority_attendee(base_time):
    candidates = [SlotCandidate(start_time=base_time, end_time=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc))]
    schedules = [
        AttendeeSchedule(email="priority@test.com", is_priority=True, busy_slots=[{"start": base_time, "end": datetime(2026, 10, 5, 10, 30, tzinfo=timezone.utc)}]),
    ]
    results = score_slot_candidates(candidates, schedules)
    assert results[0].score == 40.0


def test_back_to_back_penalty(base_time):
    candidates = [SlotCandidate(start_time=base_time, end_time=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc))]
    b2b_busy = {"start": datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc), "end": base_time}
    schedules = [
        AttendeeSchedule(email="user1@test.com", busy_slots=[b2b_busy]),
    ]
    results = score_slot_candidates(candidates, schedules)
    assert results[0].score == 90.0
    assert "1 back-to-back" in results[0].reason


def test_outside_preferred_hours():
    early_time = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
    candidates = [SlotCandidate(start_time=early_time, end_time=datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc))]
    schedules = [AttendeeSchedule(email="user1@test.com", busy_slots=[])]
    results = score_slot_candidates(candidates, schedules)
    assert results[0].score == 75.0
    assert "outside preferred hours" in results[0].reason


def test_slot_ending_after_5pm_is_outside_preferred_hours():
    start = datetime(2026, 10, 5, 16, 30, tzinfo=timezone.utc)
    candidate = SlotCandidate(
        start_time=start,
        end_time=datetime(2026, 10, 5, 17, 30, tzinfo=timezone.utc),
    )
    result = score_slot_candidates([candidate], [AttendeeSchedule(email="user@test.com")])[0]
    assert result.score == 75.0
    assert "outside preferred hours" in result.reason


def test_ranking_order(base_time):
    slot_good = SlotCandidate(start_time=base_time, end_time=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc))
    slot_bad = SlotCandidate(start_time=datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc))
    
    schedules = [
        AttendeeSchedule(
            email="user1@test.com",
            busy_slots=[{"start": datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc), "end": datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)}],
        )
    ]
    results = score_slot_candidates([slot_bad, slot_good], schedules)
    assert results[0].start_time == base_time
    assert results[0].score > results[1].score


def test_empty_candidates():
    results = score_slot_candidates([], [])
    assert results == []


def test_multiple_conflicts_accumulate(base_time):
    candidates = [SlotCandidate(start_time=base_time, end_time=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc))]
    schedules = [
        AttendeeSchedule(email="user1@test.com", busy_slots=[{"start": base_time, "end": datetime(2026, 10, 5, 10, 30, tzinfo=timezone.utc)}]),
        AttendeeSchedule(email="user2@test.com", busy_slots=[{"start": base_time, "end": datetime(2026, 10, 5, 10, 45, tzinfo=timezone.utc)}]),
    ]
    results = score_slot_candidates(candidates, schedules)
    assert results[0].score == 40.0
    assert len(results[0].conflicts) == 2
