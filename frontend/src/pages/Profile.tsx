import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { useAuth, User } from "../lib/auth";

function roleLabel(role: User["role"]): string {
  switch (role) {
    case "chairman":
      return "Chairman";
    case "principal":
      return "Principal";
    case "hod":
      return "HOD";
    case "teacher":
      return "Teacher";
    case "student":
      return "Student";
  }
}

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

const DEV_ACCOUNTS = [
  { username: "chairman", label: "Chairman", role: "chairman" },
  { username: "principal", label: "Principal", role: "principal" },
  { username: "hod", label: "HOD", role: "hod" },
  { username: "teacher", label: "Teacher", role: "teacher" },
  { username: "aniket", label: "Aniket", role: "student" },
  { username: "sujal", label: "Sujal", role: "student" },
];

export const Profile: React.FC = () => {
  const navigate = useNavigate();
  const { user, login, logout } = useAuth();
  const [switching, setSwitching] = useState(false);

  const handleSignOut = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const handleQuickSwitch = async (username: string) => {
    setSwitching(true);
    try {
      const res = await fetch("/api/v1/auth/dev/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      if (res.ok) {
        const data = await res.json();
        const meRes = await fetch("/api/v1/auth/me", {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (meRes.ok) {
          const userData = await meRes.json();
          login(data.access_token, userData);
          navigate("/");
        }
      }
    } catch {
      alert("Failed to switch development role.");
    } finally {
      setSwitching(false);
    }
  };

  return (
    <AppShell
      pageTitle="Account &amp; Role"
      pageSubtitle="University identity, access permissions, and session credentials."
    >
      {!user ? (
        <div className="py-12 font-serif italic text-ink-soft text-center text-15">
          Loading account profile…
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left: Account details (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            <div className="editorial-card space-y-6">
              <div className="flex items-center gap-4 pb-4 border-b border-rule">
                <div className="monogram w-14 h-14 rounded-sm bg-tint text-ink border border-rule font-serif text-20 font-medium">
                  {initials(user.name)}
                </div>
                <div>
                  <h3 className="font-serif text-20 text-ink">{user.name}</h3>
                  <div className="editorial-tag editorial-tag-accent mt-1">
                    {roleLabel(user.role).toUpperCase()}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-13 font-sans">
                <div className="p-3 bg-paper border border-rule rounded-sm">
                  <span className="label text-ink-faint block mb-1">Email Address</span>
                  <span className="font-serif text-ink">{user.email}</span>
                </div>
                <div className="p-3 bg-paper border border-rule rounded-sm">
                  <span className="label text-ink-faint block mb-1">System User ID</span>
                  <span className="font-mono text-ink">#{user.id}</span>
                </div>
                <div className="p-3 bg-paper border border-rule rounded-sm">
                  <span className="label text-ink-faint block mb-1">Institution Domain</span>
                  <span className="font-serif text-ink">
                    {user.email.split("@")[1] || "university.com"}
                  </span>
                </div>
                <div className="p-3 bg-paper border border-rule rounded-sm">
                  <span className="label text-ink-faint block mb-1">Account Authority</span>
                  <span className="font-serif text-ink">{roleLabel(user.role)}</span>
                </div>
              </div>
            </div>

            {/* Role Permissions Matrix */}
            <div className="editorial-card space-y-4">
              <div className="flex items-center gap-2 border-b border-rule pb-3">
                <Shield size={16} className="text-accent" />
                <h3 className="font-serif text-16 text-ink">
                  Role Authority Matrix: {roleLabel(user.role)}
                </h3>
              </div>

              <div className="space-y-2 text-13 font-sans divide-y divide-rule/60">
                <div className="pt-2 flex items-center justify-between">
                  <span className="text-ink">Create Meeting Requests</span>
                  {["chairman", "principal", "hod", "teacher"].includes(user.role) ? (
                    <span className="editorial-tag editorial-tag-ok text-9">AUTHORIZED</span>
                  ) : (
                    <span className="editorial-tag editorial-tag-default text-9">RESTRICTED</span>
                  )}
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <span className="text-ink">Approve Agendas &amp; Meeting Minutes</span>
                  {["chairman", "principal", "hod"].includes(user.role) ? (
                    <span className="editorial-tag editorial-tag-ok text-9">AUTHORIZED</span>
                  ) : (
                    <span className="editorial-tag editorial-tag-default text-9">RESTRICTED</span>
                  )}
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <span className="text-ink">Inspect Autonomous Agent Traces</span>
                  {["chairman", "principal", "hod"].includes(user.role) ? (
                    <span className="editorial-tag editorial-tag-ok text-9">AUTHORIZED</span>
                  ) : (
                    <span className="editorial-tag editorial-tag-default text-9">RESTRICTED</span>
                  )}
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <span className="text-ink">Campus Facility Administration</span>
                  {["chairman", "principal"].includes(user.role) ? (
                    <span className="editorial-tag editorial-tag-ok text-9">AUTHORIZED</span>
                  ) : (
                    <span className="editorial-tag editorial-tag-default text-9">RESTRICTED</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right: Quick Role Switcher (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            <div className="editorial-card space-y-3">
              <span className="label text-ink-faint block">Developer Role Switcher</span>
              <p className="font-sans text-12 text-ink-soft">
                Instantly switch accounts in development to test role-based permissions and approval gates:
              </p>

              <div className="space-y-1.5 pt-1">
                {DEV_ACCOUNTS.map((acc) => (
                  <button
                    key={acc.username}
                    type="button"
                    disabled={switching || user.email.startsWith(acc.username)}
                    onClick={() => handleQuickSwitch(acc.username)}
                    className={`w-full p-2.5 rounded-sm text-left flex items-center justify-between text-12 font-sans border transition-colors ${
                      user.email.startsWith(acc.username)
                        ? "bg-tint border-ink text-ink font-medium"
                        : "bg-paper border-rule text-ink-soft hover:border-ink hover:text-ink"
                    }`}
                  >
                    <span>{acc.label}</span>
                    <span className="editorial-tag editorial-tag-default text-9">
                      {acc.role.toUpperCase()}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="editorial-card space-y-3">
              <span className="label text-ink-faint block">Session Actions</span>
              <p className="font-sans text-12 text-ink-soft">
                End your authenticated session on this workstation.
              </p>
              <button
                type="button"
                onClick={handleSignOut}
                className="btn-secondary text-12 text-accent"
              >
                Sign out of account
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};
