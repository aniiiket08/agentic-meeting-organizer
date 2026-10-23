import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Printer, X } from "lucide-react";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { MeetingWorkLinks } from "../components/MeetingWorkLinks";
import { useAuth } from "../lib/auth";

interface ActionCandidate {
  title: string;
  owner_email: string;
  due_date?: string | null;
  due_date_relative?: string;
  priority: string;
  source_quote: string;
  source_timestamp?: string | null;
}

interface MinutesData {
  id: number;
  meeting_id: number;
  version: number;
  summary: string;
  key_discussion_points: string[];
  action_items: ActionCandidate[];
  status: "draft" | "approved" | "rejected";
  content_hash: string;
  transcript: string;
}

interface TranscriptLine {
  raw: string;
  timestamp: string | null;
  text: string;
  lineIndex: number;
}

function parseTranscript(raw: string): TranscriptLine[] {
  return raw.split("\n").map((line, i) => {
    const m = line.match(/^[\[(]?(\d{1,2}:\d{2}(?::\d{2})?)[\])]?\s*/);
    if (m) {
      return { raw: line, timestamp: m[1], text: line.slice(m[0].length), lineIndex: i };
    }
    return { raw: line, timestamp: null, text: line, lineIndex: i };
  });
}

function formatDueDate(item: ActionCandidate): string {
  if (item.due_date) return item.due_date;
  if (item.due_date_relative) return item.due_date_relative;
  return "No due date";
}

interface DrawerProps {
  lines: TranscriptLine[];
  highlightTimestamp: string | null;
  onClose: () => void;
}

const TranscriptDrawer: React.FC<DrawerProps> = ({ lines, highlightTimestamp, onClose }) => {
  const highlightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (highlightTimestamp && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightTimestamp]);

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} aria-hidden="true" />
      <aside className="drawer-panel" aria-label="Source transcript" role="complementary">
        <div className="drawer-header bg-surface">
          <span className="label text-ink">Source Spoken Transcript</span>
          <button
            onClick={onClose}
            className="p-1 text-ink-soft hover:text-ink transition-colors"
            aria-label="Close transcript"
          >
            <X size={16} />
          </button>
        </div>
        <div className="drawer-body font-mono text-11 leading-relaxed space-y-1">
          {lines.map((line) => {
            const isHighlight =
              highlightTimestamp !== null && line.timestamp === highlightTimestamp;
            return (
              <div
                key={line.lineIndex}
                ref={isHighlight ? highlightRef : undefined}
                className={`py-1 px-1.5 rounded-sm ${
                  isHighlight ? "transcript-line-highlight" : "hover:bg-tint/40"
                }`}
              >
                {line.timestamp && (
                  <span className="text-ink-faint mr-2 select-none font-semibold">
                    [{line.timestamp}]
                  </span>
                )}
                <span className="text-ink">{line.text}</span>
              </div>
            );
          })}
        </div>
      </aside>
    </>
  );
};

export const MinutesReview: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();

  const canProcessTranscript = !!user && ["chairman", "principal", "hod", "teacher"].includes(user.role);
  const canApproveMinutes = !!user && ["chairman", "principal", "hod"].includes(user.role);

  const [minutes, setMinutes] = useState<MinutesData | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Transcript drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [highlightTimestamp, setHighlightTimestamp] = useState<string | null>(null);

  const transcriptLines = minutes ? parseTranscript(minutes.transcript) : [];

  useEffect(() => {
    fetchMinutes();
  }, [id]);

  const fetchMinutes = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<MinutesData>(`/meetings/${id}/minutes`);
      setMinutes(data);
    } catch (err: any) {
      setMinutes(null);
      const message = err.message || "Could not load meeting minutes.";
      setError(
        message.includes("Transcript with ID")
          ? "No transcript recorded for this session yet. Provide a transcript below to extract minutes."
          : message
      );
    } finally {
      setLoading(false);
    }
  };

  const handlePasteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pasteText.trim()) return;
    setProcessing(true);
    setError(null);
    try {
      const result = await api.post<{ minutes: MinutesData }>(
        `/meetings/${id}/transcript/paste`,
        { text: pasteText }
      );
      setMinutes(result.minutes);
      setPasteText("");
      setSuccessMsg("Transcript processed. PII redacted and action items grounded.");
    } catch (err: any) {
      setError(err.message || "Could not process transcript.");
    } finally {
      setProcessing(false);
    }
  };

  const handleApprove = async () => {
    if (!minutes) return;
    setApproving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.post<any>(`/meetings/${id}/minutes/approve`, {});
      setMinutes({ ...minutes, status: "approved", content_hash: res.content_hash });
      setSuccessMsg(`Minutes approved and locked. ${res.action_count} follow-up task(s) active.`);
    } catch (err: any) {
      setError(err.message || "Could not approve minutes.");
    } finally {
      setApproving(false);
    }
  };

  const openDrawerAt = useCallback((ts: string | null) => {
    setHighlightTimestamp(ts);
    setDrawerOpen(true);
  }, []);

  return (
    <AppShell
      pageTitle="Minutes Review"
      pageSubtitle={`Session Minutes & Grounded Evidence · Meeting #${id}`}
      actionButton={
        id && (
          <div className="flex items-center gap-2 no-print">
            {minutes && (
              <button
                type="button"
                onClick={() => openDrawerAt(null)}
                className="btn-secondary text-11"
              >
                Inspect Transcript
              </button>
            )}
            <button
              type="button"
              onClick={() => window.print()}
              className="btn-secondary text-11 flex items-center gap-1"
            >
              <Printer size={13} />
              <span>Print / PDF</span>
            </button>
            <Link to={`/meetings/${id}`} className="btn-secondary text-11">
              Dossier
            </Link>
          </div>
        )
      }
    >
      <div className="space-y-6">
        {/* Work links */}
        {id && (
          <div className="no-print">
            <MeetingWorkLinks meetingId={id} />
          </div>
        )}

        {/* Messages */}
        {error && (
          <div className="error-banner no-print" role="alert">
            {error}
          </div>
        )}

        {successMsg && (
          <div className="p-3 bg-tint border-l-2 border-l-ink text-ink font-sans text-13 no-print">
            {successMsg}
          </div>
        )}

        {loading ? (
          <div className="py-16 text-center font-serif italic text-ink-soft text-15">
            Loading transcript and signed minutes…
          </div>
        ) : !minutes ? (
          /* ── Paste transcript Fallback ─────────────────────── */
          canProcessTranscript ? (
            <div className="editorial-card max-w-2xl space-y-4">
              <div className="border-b border-rule pb-3">
                <span className="label text-ink-faint block">No Recording Recorded</span>
                <h3 className="font-serif text-18 text-ink">
                  Paste Spoken Transcript
                </h3>
                <p className="font-sans text-12 text-ink-soft mt-1">
                  Paste transcript text with speaker labels and timestamps. The multi-pass minutes agent will redact PII and extract commitments.
                </p>
              </div>

              <form onSubmit={handlePasteSubmit} className="space-y-4">
                <textarea
                  rows={10}
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  placeholder="[00:00:15] Alice: Welcome everyone. Let's decide on the GPU cluster budget.&#10;[00:00:30] Bob: I suggest $50k.&#10;[00:00:45] Alice: Agreed, $50k is approved for the GPU cluster."
                  className="w-full bg-paper border border-rule rounded-sm p-3 font-mono text-12 text-ink outline-none focus:border-ink resize-y leading-relaxed"
                />

                <button
                  type="submit"
                  disabled={processing || !pasteText.trim()}
                  className="btn-primary"
                >
                  {processing ? "Synthesizing Minutes…" : "Extract Decisions & Actions"}
                </button>
              </form>
            </div>
          ) : (
            <div className="editorial-card py-16 text-center font-serif italic text-ink-soft text-15">
              Minutes are not yet available for this meeting.
            </div>
          )
        ) : (
          /* ── Official Document Presentation ────────────────── */
          <div className="space-y-6">
            {/* Meta & Status Bar (Hidden in print) */}
            <div className="editorial-card flex flex-col sm:flex-row sm:items-center justify-between gap-3 no-print">
              <div className="flex items-center gap-3">
                <span className="font-mono text-11 text-ink-faint">
                  DOCUMENT VERSION: v{minutes.version}
                </span>
                <span
                  className={`editorial-tag ${
                    minutes.status === "approved" ? "editorial-tag-ok" : "editorial-tag-warn"
                  }`}
                >
                  {minutes.status.toUpperCase()}
                </span>
              </div>

              <div className="font-mono text-10 text-ink-faint truncate max-w-xs">
                SHA256: {minutes.content_hash}
              </div>
            </div>

            {/* Document Body */}
            <div className="editorial-card p-8 print-document space-y-8 bg-paper">
              {/* Document Header */}
              <div className="border-b border-rule-strong pb-4">
                <span className="font-sans text-10 uppercase tracking-widest text-ink-faint block">
                  Official Record of Proceedings
                </span>
                <h2 className="font-serif text-28 text-ink mt-1 font-normal tracking-tight">
                  Meeting #{minutes.meeting_id} — Minutes
                </h2>
                <div className="font-mono text-11 text-ink-soft mt-1">
                  Integrity Hash: {minutes.content_hash}
                </div>
              </div>

              {/* 01 Summary */}
              <section className="space-y-2">
                <span className="label text-ink-faint block">01 — Executive Summary</span>
                <p className="font-serif text-16 text-ink leading-relaxed" style={{ maxWidth: "70ch" }}>
                  {minutes.summary}
                </p>
              </section>

              {/* 02 Discussion Points */}
              {minutes.key_discussion_points && minutes.key_discussion_points.length > 0 && (
                <section className="space-y-3 pt-4 border-t border-rule">
                  <span className="label text-ink-faint block">
                    02 — Key Deliberations
                  </span>
                  <div className="space-y-2">
                    {minutes.key_discussion_points.map((pt, idx) => (
                      <div key={idx} className="flex items-start gap-3">
                        <span className="font-mono text-11 text-ink-faint shrink-0 pt-0.5">
                          {String(idx + 1).padStart(2, "0")}
                        </span>
                        <p className="font-serif text-15 text-ink leading-relaxed">
                          {pt}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* 03 Action Items & Decisions */}
              <section className="space-y-4 pt-4 border-t border-rule">
                <div className="flex items-center justify-between">
                  <span className="label text-ink-faint block">
                    03 — Grounded Action Items ({minutes.action_items.length})
                  </span>
                </div>

                {minutes.action_items.length === 0 ? (
                  <p className="font-serif italic text-ink-soft text-14">
                    No explicit commitments or action items identified.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {minutes.action_items.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-4 bg-surface border border-rule rounded-sm space-y-2"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                          <div className="flex items-start gap-2.5">
                            <span className="font-mono text-11 text-ink-faint pt-0.5">
                              {String(idx + 1).padStart(2, "0")}
                            </span>
                            <span className="font-serif text-15 font-medium text-ink">
                              {item.title}
                            </span>
                          </div>

                          <span
                            className={`editorial-tag ${
                              item.priority === "high"
                                ? "editorial-tag-accent"
                                : "editorial-tag-default"
                            } text-9 shrink-0`}
                          >
                            {item.priority.toUpperCase()}
                          </span>
                        </div>

                        <div className="flex flex-wrap items-center gap-4 text-11 font-mono text-ink-soft pl-6">
                          <span>Owner: <strong>{item.owner_email || "Unassigned"}</strong></span>
                          <span>Deadline: <strong>{formatDueDate(item)}</strong></span>
                        </div>

                        {/* Grounded source quote */}
                        {item.source_quote && (
                          <div className="pl-6 pt-1">
                            <blockquote className="quote-block text-13 text-ink-soft my-1">
                              "{item.source_quote}"
                            </blockquote>
                            {item.source_timestamp && (
                              <button
                                type="button"
                                onClick={() => openDrawerAt(item.source_timestamp!)}
                                className="font-mono text-10 text-accent underline ml-3 no-print hover:opacity-80"
                              >
                                View in Spoken Transcript [{item.source_timestamp}]
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Approval Gate Section (No Print) */}
              <div className="pt-6 border-t border-rule-strong no-print flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <span className="label text-ink-faint block">Executive Governance</span>
                  <p className="font-sans text-12 text-ink-soft">
                    {minutes.status === "approved"
                      ? "Formally signed off and committed to repository."
                      : "Awaiting human-in-the-loop sign-off by department approver."}
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  {canApproveMinutes && minutes.status !== "approved" && (
                    <button
                      type="button"
                      onClick={handleApprove}
                      disabled={approving}
                      className="btn-primary"
                    >
                      {approving ? "Locking & Distributing…" : "Approve & Sign Minutes"}
                    </button>
                  )}

                  <Link
                    to={`/actions?meeting=${id}`}
                    className="btn-secondary text-11"
                  >
                    View in Action Tracker
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Slide-in Transcript Drawer ────────────────────────── */}
      {drawerOpen && minutes && (
        <TranscriptDrawer
          lines={transcriptLines}
          highlightTimestamp={highlightTimestamp}
          onClose={() => setDrawerOpen(false)}
        />
      )}
    </AppShell>
  );
};
