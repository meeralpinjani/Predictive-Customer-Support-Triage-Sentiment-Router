import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AuthProvider, useAuth } from "./lib/auth.jsx";
import { EventsProvider } from "./lib/events.jsx";
import { homeFor, isAgentRole } from "./lib/meta.js";
import { ToastProvider } from "./components/ui.jsx";
import AppShell from "./components/layout/AppShell.jsx";
import { ForgotPasswordPage, LoginPage, ResetPasswordPage, SignupPage, WelcomePage } from "./pages/auth/AuthPages.jsx";
import { CustomerTicketPage, HelpCentrePage, NewTicketPage, SupportHome } from "./pages/customer/CustomerPages.jsx";
import { AgentQueuePage, StaffTicketPage } from "./pages/agent/AgentPages.jsx";
import { AdminInsights, AdminOverview, AdminTuning, NotFound } from "./pages/admin/AdminPages.jsx";
import { AdminAnalytics, AdminUsers } from "./pages/admin/AdminExtras.jsx";
import { AccountPage } from "./pages/auth/AccountPage.jsx";
import { IncidentsPage, KnowledgePage, SearchPage } from "./pages/shared/SharedPages.jsx";

/** Only lets through users whose role is allowed; everyone else goes to their own home. */
function Guard({ allow, children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="min-h-screen grid place-items-center text-ink-3"><Loader2 className="w-6 h-6 animate-spin" aria-label="Loading" /></div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!user.profile_complete) return <Navigate to="/welcome" replace />;
  if (allow && !allow(user)) return <Navigate to={homeFor(user)} replace />;
  return children;
}

const isCustomer = (u) => u.role === "customer";
const isAgent = (u) => isAgentRole(u.role);
const isAdmin = (u) => u.role === "admin";
const isStaff = (u) => isAgent(u) || isAdmin(u);

function Home() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return <Navigate to={user && !user.profile_complete ? "/welcome" : homeFor(user)} replace />;
}

function Shell() {
  const { user } = useAuth();
  return (
    <Guard>
      <EventsProvider user={user}>
        <AppShell />
      </EventsProvider>
    </Guard>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/welcome" element={<WelcomePage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route element={<Shell />}>
              <Route path="/support" element={<Guard allow={isCustomer}><SupportHome /></Guard>} />
              <Route path="/support/new" element={<Guard allow={isCustomer}><NewTicketPage /></Guard>} />
              <Route path="/support/tickets/:id" element={<Guard allow={isCustomer}><CustomerTicketPage /></Guard>} />
              <Route path="/help" element={<Guard allow={isCustomer}><HelpCentrePage /></Guard>} />
              <Route path="/search" element={<Guard><SearchPage /></Guard>} />
              <Route path="/account" element={<Guard><AccountPage /></Guard>} />
              <Route path="/incidents" element={<Guard allow={isStaff}><IncidentsPage /></Guard>} />
              <Route path="/queue" element={<Guard allow={isAgent}><AgentQueuePage /></Guard>} />
              <Route path="/tickets/:id" element={<Guard allow={isStaff}><StaffTicketPage /></Guard>} />
              <Route path="/knowledge" element={<Guard allow={isStaff}><KnowledgePage /></Guard>} />
              <Route path="/admin" element={<Guard allow={isAdmin}><AdminOverview /></Guard>} />
              <Route path="/admin/insights" element={<Guard allow={isAdmin}><AdminInsights /></Guard>} />
              <Route path="/admin/analytics" element={<Guard allow={isAdmin}><AdminAnalytics /></Guard>} />
              <Route path="/admin/users" element={<Guard allow={isAdmin}><AdminUsers /></Guard>} />
              <Route path="/admin/tuning" element={<Guard allow={isAdmin}><AdminTuning /></Guard>} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  );
}
