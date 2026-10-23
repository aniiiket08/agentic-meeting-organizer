import React from "react";

export interface Slot {
  slot_index: number;
  start_time: string;
  end_time: string;
  score: number;
  reason: string;
  conflicts: string[];
  attendee_busy?: Record<string, { busy: Array<{ start: string; end: string }> }>;
}

interface SlotCardProps {
  slot: Slot;
  onSelect: (slot: Slot) => void;
  isSelecting?: boolean;
  isSelected?: boolean;
}

// ── Day-strip helpers ────────────────────────────────────────
const STRIP_START_H = 9;  // 9 AM
const STRIP_END_H   = 18; // 6 PM
const STRIP_SPAN    = (STRIP_END_H - STRIP_START_H) * 60; // 540 min

function toMinutes(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function pct(minutes: number): number {
  const clamped = Math.max(STRIP_START_H * 60, Math.min(STRIP_END_H * 60, minutes));
  return ((clamped - STRIP_START_H * 60) / STRIP_SPAN) * 100;
}

// ── Attendee busy-bar component ──────────────────────────────
const AttendeeBar: React.FC<{
  email: string;
  busyPeriods: Array<{ start: string; end: string }>;
  slotStart: string;
  slotEnd: string;
}> = ({ email, busyPeriods, slotStart, slotEnd }) => {
  const slotStartMin = toMinutes(slotStart);
  const slotEndMin   = toMinutes(slotEnd);
  const slotLeft     = pct(slotStartMin);
  const slotWidth    = pct(slotEndMin) - slotLeft;
  // Short display name
  const name = email.split("@")[0].replace(/[._]/g, " ");

  return (
    <div className="flex items-center gap-3 py-1">
      {/* Name label */}
      <span
        className="font-sans text-11 text-soft shrink-0"
        style={{ width: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        title={email}
      >
        {name}
      </span>

      {/* Strip */}
      <div className="day-strip flex-1" style={{ height: 16 }}>
        {/* Busy segments */}
        {busyPeriods.map((b, i) => {
          const left  = pct(toMinutes(b.start));
          const width = pct(toMinutes(b.end)) - left;
          if (width <= 0) return null;
          return (
            <div
              key={i}
              className="day-strip-busy"
              style={{
                position: "absolute",
                left: `${left}%`,
                width: `${width}%`,
                top: 0,
                bottom: 0,
              }}
            />
          );
        })}

        {/* Selected slot marker: brick-red vertical line */}
        <div
          className="day-strip-slot-marker"
          style={{ left: `${slotLeft}%` }}
          title="Slot start"
        />
        <div
          className="day-strip-slot-marker"
          style={{ left: `${slotLeft + slotWidth}%` }}
          title="Slot end"
        />
        {/* Slot span as a faint wash */}
        <div
          style={{
            position: "absolute",
            left: `${slotLeft}%`,
            width: `${slotWidth}%`,
            top: 0,
            bottom: 0,
            background: "var(--accent-wash)",
            opacity: 0.7,
          }}
        />
      </div>

      {/* Time labels */}
      <span className="font-mono text-10 text-faint shrink-0" style={{ width: 28 }}>
        {String(STRIP_START_H).padStart(2, "0")}
      </span>
      <span className="font-mono text-10 text-faint shrink-0" style={{ width: 28 }}>
        {String(STRIP_END_H).padStart(2, "0")}
      </span>
    </div>
  );
};

// ── SlotCard ─────────────────────────────────────────────────
export const SlotCard: React.FC<SlotCardProps> = ({
  slot,
  onSelect,
  isSelecting,
  isSelected = false,
}) => {
  const startDt = new Date(slot.start_time);
  const endDt   = new Date(slot.end_time);

  const dayLabel = startDt.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

  const timeRange = [
    startDt.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false }),
    endDt.toLocaleTimeString("en-GB",   { hour: "2-digit", minute: "2-digit", hour12: false }),
  ].join(" – ");
  const reasonText = slot.reason.includes(": ")
    ? slot.reason.slice(slot.reason.indexOf(": ") + 2)
    : slot.reason;

  const attendees = slot.attendee_busy
    ? Object.entries(slot.attendee_busy)
    : [];

  return (
    <div
      className="border-b border-rule py-5 px-2 transition-colors"
      style={{
        background: isSelected ? "var(--accent-wash)" : undefined,
        borderLeft: isSelected ? "2px solid var(--accent)" : "2px solid transparent",
        paddingLeft: isSelected ? 10 : 12,
      }}
    >
      {/* Slot header row */}
      <div className="flex items-baseline justify-between mb-2">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-11 text-faint">0{slot.slot_index}</span>
          <span
            className="font-serif text-ink"
            style={{ fontSize: 17, lineHeight: 1.4 }}
          >
            {dayLabel}
          </span>
          <span className="font-mono text-13 text-soft">{timeRange}</span>
        </div>

        <button
          onClick={() => onSelect(slot)}
          disabled={isSelecting}
          className="label text-ink hover:text-accent underline underline-offset-2 transition-colors disabled:opacity-50 ml-4 shrink-0"
        >
          {isSelecting ? "Booking…" : "Select →"}
        </button>
      </div>

      {/* Reasoning italic line */}
      <p className="font-serif italic text-13 text-soft mb-3 pl-7">
        {reasonText}
      </p>

      {/* Attendee day strips */}
      {attendees.length > 0 && (
        <div className="pl-7 space-y-0.5">
          {attendees.map(([email, data]) => (
            <AttendeeBar
              key={email}
              email={email}
              busyPeriods={data.busy}
              slotStart={slot.start_time}
              slotEnd={slot.end_time}
            />
          ))}
          {/* Time axis labels below last strip */}
          <div className="flex items-center gap-3 mt-1">
            <div style={{ width: 100 }} />
            <div className="flex justify-between flex-1 font-mono text-10 text-faint">
              <span>9:00</span>
              <span>12:00</span>
              <span>15:00</span>
              <span>18:00</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
