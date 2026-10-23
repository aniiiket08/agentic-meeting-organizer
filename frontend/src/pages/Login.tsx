import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ThemeToggle } from "../components/ThemeToggle";

const DEV_LOGIN_ROLES = [
  { username: "chairman",  label: "Chairman" },
  { username: "principal", label: "Principal" },
  { username: "hod",       label: "HOD" },
  { username: "teacher",   label: "Teacher" },
  { username: "aniket",    label: "Aniket" },
  { username: "sujal",     label: "Sujal" },
  { username: "viraj",     label: "Viraj" },
  { username: "sarvesh",   label: "Sarvesh" },
] as const;

const IS_DEV = import.meta.env?.VITE_APP_ENV === "development";

export const Login: React.FC = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  const { login } = useAuth();
  const navigate  = useNavigate();

  const completeLogin = async (token: string) => {
    const meRes = await fetch("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!meRes.ok) throw new Error("Could not load profile after sign in.");
    const userData = await meRes.json();
    login(token, userData);
    navigate("/");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || "Invalid username or password.");
      }
      const data = await res.json();
      await completeLogin(data.access_token);
    } catch (err: any) {
      setError(err.message || "The authentication service could not be reached.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (devUsername: string) => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/dev/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: devUsername }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || "Could not start a development session.");
      }
      const data = await res.json();
      await completeLogin(data.access_token);
    } catch (err: any) {
      setError(err.message || "The authentication service could not be reached.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen bg-paper flex flex-col"
      style={{ padding: "0" }}
    >
      {/* ── Main split layout ───────────────────────────────── */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12">

        {/* Left: Oversized wordmark */}
        <div
          className="lg:col-span-7 flex flex-col justify-center px-12 py-16 lg:py-24"
          style={{ borderRight: "1px solid var(--rule)" }}
        >
          <h1
            className="font-serif text-ink tracking-tight mb-6"
            style={{
              fontSize: "clamp(48px, 7vw, 96px)",
              lineHeight: "0.95",
              letterSpacing: "-0.02em",
            }}
          >
            Meeting
            <br />
            Organizer
            <sup
              className="font-sans"
              style={{ fontSize: "clamp(14px, 1.5vw, 20px)", verticalAlign: "super" }}
            >
              ™
            </sup>
          </h1>

          <p className="lead-italic max-w-sm">
            Meetings, minuted and followed through.
          </p>
        </div>

        {/* Right: Sign-in form */}
        <div className="lg:col-span-5 flex flex-col justify-center px-10 py-16 lg:py-24">
          <h2 className="label text-soft mb-8">Sign In</h2>

          {error && (
            <div className="error-banner mb-6" role="alert" aria-live="polite">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-8" noValidate>
            {/* Username field with float label */}
            <div className="field-float">
              <label htmlFor="login-username" className="field-label">
                Username
              </label>
              <input
                id="login-username"
                type="text"
                required
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-underline"
              />
            </div>

            {/* Password field with float label */}
            <div className="field-float">
              <label htmlFor="login-password" className="field-label">
                Password
              </label>
              <input
                id="login-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-underline"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary"
            >
              {loading ? "Authenticating…" : "Sign In"}
            </button>
          </form>

          {IS_DEV && (
            <div className="mt-10 pt-6 border-t border-rule">
              <p className="label text-faint mb-3">Quick Developer Sign-In</p>
              <div className="flex flex-wrap gap-2">
                {DEV_LOGIN_ROLES.map((r) => (
                  <button
                    key={r.username}
                    type="button"
                    disabled={loading}
                    onClick={() => handleQuickLogin(r.username)}
                    className="editorial-tag editorial-tag-default hover:border-ink hover:text-ink transition-colors cursor-pointer text-10 py-1 px-2 disabled:opacity-50"
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ── Footer ─────────────────────────────────────────── */}
      <footer className="page-footer no-print">
        <span>Worklet 4 · Agentic AI Lab</span>
        <ThemeToggle />
      </footer>
    </div>
  );
};
