import React from "react";
import { useNavigate } from "react-router-dom";
import { meetingTasksPath } from "./MeetingWorkLinks";

const STAGES = [
  { key: "schedule", label: "Schedule" },
  { key: "agenda",   label: "Agenda"   },
  { key: "meeting",  label: "Meeting"  },
  { key: "minutes",  label: "Minutes"  },
  { key: "actions",  label: "Actions"  },
] as const;

function statusToStage(status: string): number {
  switch (status) {
    case "requested":
    case "slots_proposed":
      return 0; // Schedule active
    case "room_booked":
    case "scheduled":
      return 1; // Agenda active
    case "agenda_drafted":
    case "agenda_approved":
      return 2; // Meeting active
    case "transcript_uploaded":
    case "minutes_drafted":
      return 3; // Minutes active
    case "minutes_approved":
      return 4; // Actions active
    default:
      return 0;
  }
}

interface Props {
  status: string;
  meetingId?: number;
  className?: string;
}

function stagePath(meetingId: number, key: (typeof STAGES)[number]["key"]): string {
  if (key === "agenda" || key === "schedule" || key === "meeting") {
    return `/meetings/${meetingId}/agenda`;
  }
  if (key === "minutes") return `/meetings/${meetingId}/minutes`;
  return meetingTasksPath(meetingId);
}

export const StageTracker: React.FC<Props> = ({ status, meetingId, className = "" }) => {
  const activeIdx = statusToStage(status);
  const navigate = useNavigate();

  return (
    <div className={`${className}`} aria-label="Meeting stage">
      {/* Rule with markers */}
      <div className="stage-track" role="list">
        {STAGES.map((stage, idx) => (
          <React.Fragment key={stage.key}>
            <button
              type="button"
              className={`stage-marker${idx < activeIdx ? " done" : idx === activeIdx ? " active" : ""}`}
              role="listitem"
              aria-label={`${stage.label}: ${idx < activeIdx ? "done" : idx === activeIdx ? "current" : "upcoming"}`}
              disabled={!meetingId}
              onClick={(event) => {
                event.stopPropagation();
                if (meetingId) navigate(stagePath(meetingId, stage.key));
              }}
            />
            {idx < STAGES.length - 1 && <div className="stage-connector" />}
          </React.Fragment>
        ))}
      </div>

      {/* Labels under each marker */}
      <div className="flex mt-1.5" style={{ gap: 0 }}>
        {STAGES.map((stage, idx) => (
          <React.Fragment key={stage.key}>
            <div
              className="flex justify-center"
              style={{ width: 10, flexShrink: 0 }}
            >
              <span
                className="label"
                style={{
                  fontSize: 9,
                  color:
                    idx < activeIdx
                      ? "var(--ink-faint)"
                      : idx === activeIdx
                      ? "var(--accent)"
                      : "var(--ink-faint)",
                  transform: "translateX(-50%)",
                  display: "block",
                  whiteSpace: "nowrap",
                  position: "relative",
                  left: "50%",
                }}
              >
                {stage.label}
              </span>
            </div>
            {idx < STAGES.length - 1 && <div style={{ flex: 1 }} />}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
