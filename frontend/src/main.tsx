import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth, User } from "./lib/auth";
import { ActionTracker } from "./pages/ActionTracker";
import { Admin } from "./pages/Admin";
import { AgendaEditor } from "./pages/AgendaEditor";
import { Dashboard } from "./pages/Dashboard";
import { Evaluations } from "./pages/Evaluations";
import { Login } from "./pages/Login";
import { MeetingDetails } from "./pages/MeetingDetails";
import { MeetingsList } from "./pages/MeetingsList";
import { MemoryChat } from "./pages/MemoryChat";
import { MinutesReview } from "./pages/MinutesReview";
import { NewMeeting } from "./pages/NewMeeting";
import { Profile } from "./pages/Profile";
import { Schedule } from "./pages/Schedule";
import { TraceViewer } from "./pages/TraceViewer";
import "./index.css";

const ProtectedRoute: React.FC<{
  children: React.ReactNode;
  allowedRoles?: User["role"][];
}> = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center font-serif text-soft">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/meetings"
            element={
              <ProtectedRoute>
                <MeetingsList />
              </ProtectedRoute>
            }
          />
          <Route
            path="/meetings/new"
            element={
              <ProtectedRoute allowedRoles={["chairman", "principal", "hod", "teacher"]}>
                <NewMeeting />
              </ProtectedRoute>
            }
          />
          <Route
            path="/meetings/:id"
            element={
              <ProtectedRoute>
                <MeetingDetails />
              </ProtectedRoute>
            }
          />
          <Route
            path="/meetings/:id/agenda"
            element={
              <ProtectedRoute>
                <AgendaEditor />
              </ProtectedRoute>
            }
          />
          <Route
            path="/meetings/:id/minutes"
            element={
              <ProtectedRoute>
                <MinutesReview />
              </ProtectedRoute>
            }
          />
          <Route
            path="/actions"
            element={
              <ProtectedRoute>
                <ActionTracker />
              </ProtectedRoute>
            }
          />
          <Route
            path="/schedule"
            element={
              <ProtectedRoute allowedRoles={["chairman", "principal", "hod", "teacher"]}>
                <Schedule />
              </ProtectedRoute>
            }
          />
          <Route
            path="/memory"
            element={
              <ProtectedRoute>
                <MemoryChat />
              </ProtectedRoute>
            }
          />
          <Route
            path="/traces"
            element={
              <ProtectedRoute allowedRoles={["chairman", "principal", "hod"]}>
                <TraceViewer />
              </ProtectedRoute>
            }
          />
          <Route
            path="/evaluations"
            element={
              <ProtectedRoute>
                <Evaluations />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={["chairman", "principal"]}>
                <Admin />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
);
