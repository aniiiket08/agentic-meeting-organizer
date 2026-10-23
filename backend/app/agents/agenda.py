import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import NotFound, ToolError, ValidationFailed
from app.core.logging import logger
from app.db.models.action import ActionItem, ActionStatus
from app.db.models.meeting import Attendee, Meeting
from app.db.models.user import User
from app.memory.vector_store import memory_store
from app.observability.tracer import record_tool_call, trace_agent
from app.services.llm import llm_service


class AgendaItemSchema(BaseModel):
    item_number: int = Field(ge=1, description="1-based item number")
    title: str = Field(min_length=1, description="Topic item title")
    owner: str = Field(min_length=1, description="Assigned item owner or lead")
    duration_minutes: int = Field(gt=0, description="Time box in minutes")
    unresolved_context: str | None = Field(default=None, description="Context from past meetings or open actions")
    source: str = Field(default="user", description="Where the item came from: 'user' | 'llm_closing'")


class CarriedOverItemSchema(BaseModel):
    description: str = Field(min_length=1)
    source_meeting_title: str | None = Field(default=None)
    action_id: int | None = Field(default=None)


class TimeboxedAgendaSchema(BaseModel):
    meeting_title: str
    total_duration_minutes: int
    items: list[AgendaItemSchema]
    carried_over: list[CarriedOverItemSchema] = Field(default_factory=list)
    is_purpose_draft: bool = Field(default=False, description="True when no user items were supplied")
    draft_warning: str | None = Field(default=None, description="Optional warning shown when purpose-drafted")
    validation_warnings: list[str] = Field(default_factory=list)
    llm_retries: int = Field(default=0, description="How many times the LLM output was retried because it violated user items")
    fallback_applied: bool = Field(default=False, description="True if a deterministic fallback was used")


@dataclass
class ParsedUserItem:
    title: str
    owner_raw: str | None
    duration_minutes: int | None


_USER_ITEM_RE = re.compile(r"\s*\|\s*")
_MINUTE_RE = re.compile(r"^\s*(\d+)\s*(?:m|min|mins|minutes)?\s*$", re.IGNORECASE)


def parse_user_items_text(raw_text: str) -> list[ParsedUserItem]:
    """Parse the pipe-delimited Agenda items text.

    Format (per line):
        Title [ | Owner list ] [ | minutes ]
    """
    if not raw_text:
        return []
    parsed: list[ParsedUserItem] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in _USER_ITEM_RE.split(line)]
        title = parts[0].strip()
        if not title:
            continue
        owner_raw: str | None = None
        duration_minutes: int | None = None
        if len(parts) >= 2 and parts[1]:
            maybe_owner = parts[1].strip()
            m = _MINUTE_RE.match(maybe_owner)
            if m:
                duration_minutes = int(m.group(1))
            else:
                owner_raw = maybe_owner
        if len(parts) >= 3 and parts[2] and duration_minutes is None:
            m = _MINUTE_RE.match(parts[2].strip())
            if m:
                duration_minutes = int(m.group(1))
        parsed.append(
            ParsedUserItem(
                title=title,
                owner_raw=owner_raw,
                duration_minutes=duration_minutes,
            )
        )
    return parsed


def _has_next_steps_item(items: list[ParsedUserItem]) -> bool:
    normalized = [re.sub(r"[\s\-_:]+", " ", i.title.lower()).strip() for i in items]
    markers = {"next steps", "next step", "action items", "follow up", "followup", "closing"}
    return any(any(marker in n for marker in markers) for n in normalized)


def _attendee_display_names(db: Session, meeting: Meeting) -> list[str]:
    rows = (
        db.query(Attendee, User)
        .outerjoin(User, Attendee.user_id == User.id)
        .filter(Attendee.meeting_id == meeting.id)
        .all()
    )
    names: list[str] = []
    for _att, user in rows:
        if user:
            if user.name:
                names.append(user.name)
        elif _att.external_email:
            names.append(_att.external_email.split("@")[0])
    return list(dict.fromkeys(names))  # preserve order, dedupe


def _split_duration_evenly(total: int, count: int, priority_indices: list[int] | None = None) -> list[int]:
    """Distribute total minutes across count items; priority_indices get 1-minute carry-over."""
    if count <= 0:
        return []
    base = total // count
    result = [base] * count
    remainder = total - base * count
    order = list(priority_indices or range(count))
    for i in range(remainder):
        idx = order[i % len(order)] if order else i % count
        result[idx] += 1
    return [max(1, v) for v in result]


def _build_fallback_items(
    meeting_duration: int,
    user_items: list[ParsedUserItem],
    attendee_names: list[str],
    add_closing: bool,
) -> list[AgendaItemSchema]:
    """Deterministic fallback: keep user items verbatim, split time evenly, blank owners as TBD."""
    core_count = len(user_items) + (1 if add_closing else 0)
    durations = _split_duration_evenly(meeting_duration, core_count)
    out: list[AgendaItemSchema] = []
    for idx, u_item in enumerate(user_items):
        owner = u_item.owner_raw or "TBD"
        duration = u_item.duration_minutes or durations[idx]
        out.append(
            AgendaItemSchema(
                item_number=len(out) + 1,
                title=u_item.title,
                owner=owner,
                duration_minutes=duration,
                source="user",
            )
        )
    if add_closing:
        closing_index = len(user_items)
        out.append(
            AgendaItemSchema(
                item_number=len(out) + 1,
                title="Next steps",
                owner=attendee_names[0] if attendee_names else "TBD",
                duration_minutes=durations[closing_index],
                source="llm_closing",
            )
        )
    # Re-balance if any user items had explicit durations already set
    total_so_far = sum(i.duration_minutes for i in out)
    if total_so_far != meeting_duration:
        delta = meeting_duration - total_so_far
        # Apply delta to the last item (that isn't explicitly fixed if possible)
        candidates = list(range(len(out)))
        for idx in reversed(candidates):
            if out[idx].source == "user" and user_items[idx if idx < len(user_items) else 0].duration_minutes is not None:
                continue
            out[idx] = out[idx].model_copy(update={
                "duration_minutes": max(1, out[idx].duration_minutes + delta),
            })
            break
        else:
            # All items are fixed; adjust last item anyway
            out[-1] = out[-1].model_copy(update={
                "duration_minutes": max(1, out[-1].duration_minutes + delta),
            })
    return out


def _validate_agenda_against_user_items(
    items: list[AgendaItemSchema],
    user_items: list[ParsedUserItem],
    attendees: list[str],
    meeting_duration: int,
) -> tuple[bool, list[str]]:
    """Return (OK, list of violations)."""
    violations: list[str] = []
    if not user_items:
        return True, violations
    if len(items) < len(user_items):
        violations.append(
            f"LLM output has {len(items)} items but user provided {len(user_items)}; missing items."
        )
    for idx, expected in enumerate(user_items):
        if idx >= len(items):
            break
        actual_title = items[idx].title.strip()
        if actual_title != expected.title:
            violations.append(
                f"Item #{idx + 1} does not match. Expected '{expected.title}' but got '{actual_title}'."
            )
    total = sum(i.duration_minutes for i in items)
    if total != meeting_duration:
        violations.append(
            f"Total minutes {total} do not equal meeting duration {meeting_duration}."
        )
    allowed_owners = set(attendees) | {"TBD"}
    for idx, it in enumerate(items):
        # If an explicit owner was provided by user, accept whatever the user wrote even if not in attendee list
        expected_owner_raw = user_items[idx].owner_raw if idx < len(user_items) else None
        if expected_owner_raw:
            # Validate owner matches at least a subset of expected names when not empty/user-supplied
            continue
        # Otherwise the LLM should pick from attendees or TBD
        if it.owner and it.owner not in allowed_owners:
            parts = {p.strip() for p in re.split(r"[,&+]", it.owner) if p.strip()}
            if not parts.issubset(allowed_owners):
                violations.append(
                    f"Item #{idx + 1} owner '{it.owner}' is not in the attendee list "
                    f"({sorted(allowed_owners)})."
                )
    return (len(violations) == 0), violations


def _extract_carried_over(
    db: Session,
    meeting_title: str,
    memory_context: str,
) -> list[CarriedOverItemSchema]:
    """Pull carried-over open actions that belong to the meeting's attendees or match memory."""
    open_actions = (
        db.query(ActionItem)
        .filter(ActionItem.status != ActionStatus.COMPLETED)
        .limit(20)
        .all()
    )
    carried: list[CarriedOverItemSchema] = []
    seen: set[str] = set()
    meeting_lower = meeting_title.lower()
    for a in open_actions:
        key = a.description.lower().strip()
        if not key or key in seen:
            continue
        # Keep if any token overlap with the meeting title
        tokens = {t for t in re.split(r"\W+", meeting_lower) if len(t) >= 3}
        a_tokens = set(re.split(r"\W+", key))
        if tokens and tokens & a_tokens:
            seen.add(key)
            owner_name = a.owner.name if a.owner else None
            src = a.source_meeting.title if hasattr(a, "source_meeting") and a.source_meeting else None
            carried.append(
                CarriedOverItemSchema(
                    description=(owner_name and f"{owner_name}: {a.description}") or a.description,
                    source_meeting_title=src,
                    action_id=a.id,
                )
            )
    # Cap at 5 carried items to keep agenda lean
    return carried[:5]


@trace_agent(agent_name="agenda_agent")
def run_agenda_agent(
    db: Session,
    meeting_id: int,
    agenda_items_text: str | None = None,
) -> TimeboxedAgendaSchema:
    """Agenda Agent: STRICTLY preserves user items when provided.

    Behavior (per project spec):
    1. If the user provided items (one per line, pipe-separated optional lead | minutes):
       - items contain EXACTLY those titles, same order, same wording; LLMs may only assign missing
         duration (totalling meeting duration) and missing leads (from the attendee list); plus a
         single 'Next steps' closing item if the user did not include one.
       - carried-over actions appear in a separate "Carried over" section.
    2. If the user provided no items: generate from title + purpose only, mark the agenda as
       `is_purpose_draft=True` with a warning banner; never pull seed/historical titles into the
       main item list.
    3. Post-generation validation: compare the LLM output against the user items verbatim. On any
       violation, retry the LLM once with the violation list included. If it still fails, apply a
       deterministic fallback (titles as-is, durations split evenly, owners = TBD or attendee[0]
       for the closing) and set fallback_applied = True.
    4. Log final prompt and LLM result in agent_runs via the tracer.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting is None:
        raise NotFound(entity="Meeting", identifier=meeting_id)

    title = meeting.title
    description = meeting.description or ""
    meeting_duration = meeting.duration_minutes
    user_items = parse_user_items_text(agenda_items_text or "")
    attendee_names = _attendee_display_names(db, meeting)
    add_closing = not _has_next_steps_item(user_items)

    # 1. Memory retrieval (used for Carried over section and context only; never for item titles
    #    when the user supplied items)
    try:
        retrieved_docs = memory_store.search(query=f"{title} {description}", top_k=2)
    except Exception as exc:
        logger.exception("Past-meeting memory retrieval failed")
        raise ToolError("Could not retrieve past meeting context.", tool_name="memory_store.search") from exc
    record_tool_call(
        "memory_store.search",
        {"query": f"{title} {description}", "top_k": 2},
        {"meeting_titles": [doc.get("title") for doc in retrieved_docs]},
    )
    memory_context = "\n".join(
        [f"- Past Meeting: {d['title']} ({d['date']}): {d['text']}" for d in retrieved_docs]
    )

    carried_over = _extract_carried_over(db, title, memory_context)

    if not user_items:
        # 2. Purpose-draft: the LLM is allowed to propose topics.
        prompt = (
            f"Draft a structured time-boxed agenda for meeting: '{title}'.\n"
            f"Meeting Duration: {meeting_duration} minutes.\n"
            f"Description: {description or 'None provided'}\n\n"
            f"Attendees (use as leads only from this list): {attendee_names or ['Chair']}.\n\n"
            f"IMPORTANT: No user items were provided. Use ONLY the title + description above to draft topics. "
            f"Do NOT insert fixed seed topics such as 'Review project status', 'GPU cluster budget', "
            f"'Safety design' or any topic from unrelated past meetings. Keep items relevant to this "
            f"meeting's purpose. Total minutes across items MUST equal {meeting_duration}. "
            f"If the description is empty, keep it to 3-6 standard items: Kick off, Discussion, Work, Review, "
            f"Risks, Next steps. Add 'Next steps' as the last item."
        )
        record_tool_call(
            "agenda_agent.prompt",
            {"mode": "purpose_draft", "meeting_id": meeting_id},
            {"prompt": prompt, "attendees": attendee_names, "carried_over_count": len(carried_over)},
        )

        agenda = llm_service.generate_structured(
            prompt=prompt,
            response_schema=TimeboxedAgendaSchema,
            system_prompt=(
                "You are an expert meeting preparation agent. Propose agenda items based on the "
                "meeting title and purpose only. Keep titles short and plain; no corporate jargon."
            ),
        )
        total_minutes = sum(item.duration_minutes for item in agenda.items)
        if not agenda.items:
            raise ValidationFailed("Agenda generation returned no agenda items.")
        # Normalize duration: if LLM over/under shoots, redistribute on the last item to exactly match
        delta = meeting_duration - total_minutes
        if delta:
            agenda.items[-1] = agenda.items[-1].model_copy(update={
                "duration_minutes": max(1, agenda.items[-1].duration_minutes + delta),
            })
            total_minutes = sum(i.duration_minutes for i in agenda.items)
        agenda.meeting_title = title
        agenda.total_duration_minutes = total_minutes
        agenda.carried_over = carried_over
        agenda.is_purpose_draft = True
        agenda.draft_warning = "Drafted from purpose, please review."
        # Renumber items so they match the list order regardless of LLM
        for idx, it in enumerate(agenda.items):
            agenda.items[idx] = it.model_copy(update={"item_number": idx + 1})
        return agenda

    # 3. Strict mode: user items provided. Build prompt and validate strictly.
    user_items_verbatim_block = "\n".join(
        f"  {idx+1}. {u.title}{(' | ' + u.owner_raw) if u.owner_raw else ''}"
        f"{(' | ' + str(u.duration_minutes)) if u.duration_minutes else ''}"
        for idx, u in enumerate(user_items)
    )
    prompt_template = (
        f"Generate a structured time-boxed agenda for meeting: '{title}'.\n"
        f"Meeting Duration: {meeting_duration} minutes.\n"
        f"Description: {description or 'None provided'}\n"
        f"Attendees (you can only pick leads from this list; use 'TBD' if unsure): {attendee_names or ['TBD']}.\n\n"
        f"USER-PROVIDED AGENDA ITEMS — TREAT AS FIXED. DO NOT ADD, REMOVE, RENAME, MERGE, OR REORDER THEM.\n"
        f"The items below MUST appear verbatim, in this exact order, as the first {len(user_items)} items of the output:\n"
        f"{user_items_verbatim_block}\n\n"
        f"What you MAY change:\n"
        f"- Assign duration_minutes to items whose user row did not include a minute count. Total MUST sum EXACTLY to {meeting_duration}.\n"
        f"- Assign owner (lead) where the user did not specify one; pick only from the attendee list.\n"
        f"- Add exactly one closing 'Next steps' item at the END if the user list did not include one.\n\n"
        f"The closing 'Next steps' item (if added) is the ONLY extra item allowed above the user list.\n"
    )

    def _run_llm_and_validate(extra_hint: str = "") -> tuple[TimeboxedAgendaSchema, list[str], int]:
        retries = 0
        prompt = prompt_template + (f"\n\nPREVIOUS OUTPUT VIOLATIONS TO FIX:\n{extra_hint}" if extra_hint else "")
        record_tool_call(
            "agenda_agent.prompt",
            {"mode": "strict_user_items", "meeting_id": meeting_id, "retries": retries},
            {"prompt": prompt},
        )
        agenda = llm_service.generate_structured(
            prompt=prompt,
            response_schema=TimeboxedAgendaSchema,
            system_prompt=(
                "You are a precise meeting preparation agent. Preserve user agenda items verbatim. "
                "Do not invent topics."
            ),
        )
        agenda.meeting_title = title
        # Renumber to list order before validation
        for idx, it in enumerate(agenda.items):
            agenda.items[idx] = it.model_copy(update={"item_number": idx + 1})
        ok, violations = _validate_agenda_against_user_items(
            items=agenda.items,
            user_items=user_items,
            attendees=attendee_names,
            meeting_duration=meeting_duration,
        )
        return agenda, violations, retries

    agenda, violations, retries = _run_llm_and_validate("")
    if violations:
        # Retry once with explicit violation list
        agenda, violations2, _ = _run_llm_and_validate("\n".join(f"- {v}" for v in violations))
        retries = 1
        violations = violations2

    fallback_applied = False
    if violations:
        fallback_applied = True
        items = _build_fallback_items(
            meeting_duration=meeting_duration,
            user_items=user_items,
            attendee_names=attendee_names,
            add_closing=add_closing,
        )
        total_minutes = sum(i.duration_minutes for i in items)
        agenda = TimeboxedAgendaSchema(
            meeting_title=title,
            total_duration_minutes=total_minutes,
            items=items,
            carried_over=carried_over,
            validation_warnings=[
                "Agenda validation failed; applied deterministic fallback with user items verbatim.",
                *violations,
            ],
            llm_retries=retries,
            fallback_applied=True,
        )
    else:
        # Final duration rebalance (exact) if user items had explicit durations already
        total_minutes = sum(i.duration_minutes for i in agenda.items)
        if total_minutes != meeting_duration and len(agenda.items) > 0:
            delta = meeting_duration - total_minutes
            # Adjust the LLM-supplied closing item first, else the last item
            target = -1
            for i in range(len(agenda.items) - 1, -1, -1):
                if agenda.items[i].source == "llm_closing":
                    target = i
                    break
            # If no explicit closing item, prefer items where user didn't give a duration
            if target == -1:
                for i in range(len(agenda.items) - 1, -1, -1):
                    ui = user_items[i] if i < len(user_items) else None
                    if ui and ui.duration_minutes is None:
                        target = i
                        break
            if target == -1:
                target = len(agenda.items) - 1
            agenda.items[target] = agenda.items[target].model_copy(update={
                "duration_minutes": max(1, agenda.items[target].duration_minutes + delta),
            })
            agenda.total_duration_minutes = sum(i.duration_minutes for i in agenda.items)
        agenda.carried_over = carried_over
        agenda.llm_retries = retries
        agenda.fallback_applied = False

    # Make sure the close item (if added via LLM) is marked as llm_closing
    for i, it in enumerate(agenda.items):
        if i >= len(user_items) and re.sub(r"[\s\-_:]+", " ", it.title.lower()).strip() in {
            "next steps", "next step", "closing", "action items"
        }:
            agenda.items[i] = it.model_copy(update={"source": "llm_closing"})

    # If user supplied an explicit lead name, do not override it even if not in attendee list
    for idx, u in enumerate(user_items):
        if idx >= len(agenda.items):
            break
        if u.owner_raw:
            cur = agenda.items[idx]
            agenda.items[idx] = cur.model_copy(update={"owner": u.owner_raw})

    return agenda
