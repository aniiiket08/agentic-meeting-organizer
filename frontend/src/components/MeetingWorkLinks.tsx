import React from "react";
import { Link, useLocation } from "react-router-dom";

type Props = {
  meetingId: number | string;
  className?: string;
};

export function meetingTasksPath(meetingId: number | string): string {
  return `/actions?meeting=${meetingId}`;
}

export const MeetingWorkLinks: React.FC<Props> = ({ meetingId, className = "" }) => {
  const location = useLocation();
  const links = [
    { label: "Agenda", path: `/meetings/${meetingId}/agenda` },
    { label: "Minutes", path: `/meetings/${meetingId}/minutes` },
    { label: "Action Items", path: meetingTasksPath(meetingId) },
  ];

  return (
    <nav
      className={`work-links ${className}`}
      aria-label="Meeting options"
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => event.stopPropagation()}
    >
      {links.map((link) => {
        const active = link.path.startsWith("/actions")
          ? location.pathname === "/actions"
          : location.pathname === link.path;
        return (
          <Link
            key={link.path}
            to={link.path}
            className={`work-link${active ? " is-active" : ""}`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
};
