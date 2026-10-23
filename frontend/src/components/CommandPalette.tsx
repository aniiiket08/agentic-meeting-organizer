import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/useTheme";

export type CmdCategory = "Navigation" | "Actions" | "Meetings";

export interface CmdItem {
  id: string;
  label: string;
  category: CmdCategory;
  shortcut?: string;
  path?: string;
  action?: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export const CommandPalette: React.FC<Props> = ({ open, onClose }) => {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [meetings, setMeetings] = useState<Array<{ id: number; title: string; status: string }>>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [theme, toggleTheme] = useTheme();

  // Load meetings for quick jump
  useEffect(() => {
    if (open) {
      api.get<Array<{ id: number; title: string; status: string }>>("/meetings")
        .then((data) => setMeetings(data.slice(0, 8)))
        .catch(() => {});
    }
  }, [open]);

  // Static items configured by role
  const canSchedule = user && ["chairman", "principal", "hod", "teacher"].includes(user.role);
  const canObserve = user && ["chairman", "principal", "hod"].includes(user.role);
  const canAdmin = user && ["chairman", "principal"].includes(user.role);

  const baseItems: CmdItem[] = [
    { id: "p-home", label: "Home / Overview", category: "Navigation" as const, path: "/", shortcut: "G H" },
    { id: "p-meetings", label: "Meetings Directory", category: "Navigation" as const, path: "/meetings", shortcut: "G M" },
    ...(canSchedule ? [{ id: "p-schedule", label: "Weekly Schedule & Timetable", category: "Navigation" as const, path: "/schedule", shortcut: "G S" }] : []),
    { id: "p-actions", label: "Tasks & Action Items", category: "Navigation" as const, path: "/actions", shortcut: "G T" },
    { id: "p-memory", label: "Memory Chat & Past Records", category: "Navigation" as const, path: "/memory", shortcut: "G C" },
    ...(canObserve ? [{ id: "p-traces", label: "Agent Traces & Telemetry", category: "Navigation" as const, path: "/traces", shortcut: "G A" }] : []),
    { id: "p-evals", label: "System Evaluations & Benchmarks", category: "Navigation" as const, path: "/evaluations", shortcut: "G E" },
    ...(canAdmin ? [{ id: "p-admin", label: "Administration & Rooms", category: "Navigation" as const, path: "/admin" }] : []),
    { id: "p-profile", label: "Profile & Role Settings", category: "Navigation" as const, path: "/profile", shortcut: "G P" },

    // Actions
    ...(canSchedule ? [{ id: "a-new-meeting", label: "+ Schedule New Meeting", category: "Actions" as const, path: "/meetings/new" }] : []),
    {
      id: "a-toggle-theme",
      label: `Switch Theme to ${theme === "light" ? "Dark" : "Light"} Mode`,
      category: "Actions" as const,
      action: () => toggleTheme(),
    },
    {
      id: "a-my-tasks",
      label: "View My Assigned Open Tasks",
      category: "Actions" as const,
      path: "/actions?status=pending",
    },
    {
      id: "a-signout",
      label: "Sign Out",
      category: "Actions" as const,
      action: () => {
        logout();
        navigate("/login");
      },
    },
  ];

  // Dynamic meeting items
  const meetingItems: CmdItem[] = meetings.map((m) => ({
    id: `m-${m.id}`,
    label: `${m.title} (Meeting #${m.id})`,
    category: "Meetings" as const,
    path: `/meetings/${m.id}`,
  }));

  const allItems = [...baseItems, ...meetingItems];

  const results = query.trim()
    ? allItems.filter(
        (item) =>
          item.label.toLowerCase().includes(query.toLowerCase()) ||
          item.category.toLowerCase().includes(query.toLowerCase())
      )
    : allItems;

  const handleSelect = useCallback(
    (item: CmdItem) => {
      onClose();
      setQuery("");
      if (item.action) {
        item.action();
      } else if (item.path) {
        navigate(item.path);
      }
    },
    [navigate, onClose]
  );

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelected(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected((s) => Math.min(s + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results[selected]) handleSelect(results[selected]);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="cmd-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-label="Command palette"
      aria-modal="true"
    >
      <div className="cmd-box shadow-lg" role="combobox" aria-expanded="true">
        <div className="flex items-center px-4 border-b border-rule">
          <span className="font-mono text-12 text-ink-faint mr-2">⌘</span>
          <input
            ref={inputRef}
            className="cmd-input py-3"
            placeholder="Type a command, search meetings, or jump to page…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label="Search"
            autoComplete="off"
          />
          <span className="font-mono text-10 text-ink-faint bg-tint px-1.5 py-0.5 rounded-sm">ESC</span>
        </div>

        <div className="max-h-80 overflow-y-auto py-2" id="cmd-results">
          {results.length === 0 ? (
            <div className="py-8 text-center font-serif italic text-14 text-ink-soft">
              No matching commands or meetings found.
            </div>
          ) : (
            results.map((item, idx) => (
              <div
                key={item.id}
                className={`cmd-item flex items-center justify-between px-4 py-2 text-13 cursor-pointer ${
                  selected === idx ? "selected bg-tint text-ink" : "text-ink-soft"
                }`}
                onMouseEnter={() => setSelected(idx)}
                onClick={() => handleSelect(item)}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="editorial-tag editorial-tag-default text-9">{item.category}</span>
                  <span className="font-sans text-13 text-ink truncate">{item.label}</span>
                </div>
                {item.shortcut && (
                  <span className="font-mono text-10 text-ink-faint bg-paper border border-rule px-1 py-0.5 rounded-sm ml-2">
                    {item.shortcut}
                  </span>
                )}
              </div>
            ))
          )}
        </div>

        <div className="px-4 py-2 border-t border-rule bg-surface flex items-center justify-between text-11 text-ink-faint font-sans">
          <span>Use ↑ ↓ to navigate · Enter to select</span>
          <span className="font-mono">Meeting Organizer Omnibar</span>
        </div>
      </div>
    </div>
  );
};
