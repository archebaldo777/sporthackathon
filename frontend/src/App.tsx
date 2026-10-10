import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { CabinetLayout, PublicLayout } from "@/components/layout/Layouts";
import { PageLoader } from "@/components/ui";
import { homeFor, useAuth } from "@/lib/auth";

const Landing = lazy(() => import("@/pages/public/Landing"));
const How = lazy(() => import("@/pages/public/How"));
const Mechanics = lazy(() => import("@/pages/public/Mechanics"));
const Validation = lazy(() => import("@/pages/public/Validation"));
const Verify = lazy(() => import("@/pages/public/Verify"));
const Auth = lazy(() => import("@/pages/public/Auth"));

const CDashboard = lazy(() => import("@/pages/candidate/Dashboard"));
const CProfile = lazy(() => import("@/pages/candidate/Profile"));
const CAssessment = lazy(() => import("@/pages/candidate/Assessment"));
const CTest = lazy(() => import("@/pages/candidate/TestRunner"));
const CResult = lazy(() => import("@/pages/candidate/AttemptResult"));
const CInvitations = lazy(() => import("@/pages/candidate/Invitations"));
const CJobs = lazy(() => import("@/pages/candidate/Jobs"));
const CApplications = lazy(() => import("@/pages/candidate/Applications"));
const CTasks = lazy(() => import("@/pages/candidate/Tasks"));
const CGrowth = lazy(() => import("@/pages/candidate/Growth"));
const CSettings = lazy(() => import("@/pages/candidate/Settings"));

const EDashboard = lazy(() => import("@/pages/employer/Dashboard"));
const ENeeds = lazy(() => import("@/pages/employer/Needs"));
const ENeedForm = lazy(() => import("@/pages/employer/NeedForm"));
const ENeedDetail = lazy(() => import("@/pages/employer/NeedDetail"));
const ETalent = lazy(() => import("@/pages/employer/Talent"));
const ECandidate = lazy(() => import("@/pages/employer/CandidateView"));
const EInvitations = lazy(() => import("@/pages/employer/Invitations"));
const EVacancies = lazy(() => import("@/pages/employer/Vacancies"));
const ETasks = lazy(() => import("@/pages/employer/Tasks"));
const ECompany = lazy(() => import("@/pages/employer/Company"));
const EIntegrations = lazy(() => import("@/pages/employer/Integrations"));

function Guard({ role, children }: { role: "candidate" | "employer"; children: ReactNode }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <PageLoader />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (!user.email_verified) return <Navigate to="/verify-email" replace />;
  if (user.role !== role) return <Navigate to={homeFor(user)} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Landing />} />
          <Route path="how" element={<How />} />
          <Route path="mechanics" element={<Mechanics />} />
          <Route path="validation" element={<Validation />} />
          <Route path="verify/:token" element={<Verify />} />
          <Route path="jobs" element={<CJobs publicMode />} />
          <Route path="jobs/:id" element={<CJobs publicMode />} />
          <Route path="login" element={<Auth mode="login" />} />
          <Route path="register" element={<Auth mode="register" />} />
          <Route path="verify-email" element={<Auth mode="verify" />} />
          <Route path="auth/fsp/callback" element={<Auth mode="fsp" />} />
        </Route>
        <Route path="c" element={<Guard role="candidate"><CabinetLayout role="candidate" /></Guard>}>
          <Route index element={<CDashboard />} />
          <Route path="profile" element={<CProfile />} />
          <Route path="assessment" element={<CAssessment />} />
          <Route path="assessment/test/:id" element={<CTest />} />
          <Route path="assessment/result/:id" element={<CResult />} />
          <Route path="invitations" element={<CInvitations />} />
          <Route path="invitations/:id" element={<CInvitations />} />
          <Route path="jobs" element={<CJobs />} />
          <Route path="jobs/:id" element={<CJobs />} />
          <Route path="applications" element={<CApplications />} />
          <Route path="tasks" element={<CTasks />} />
          <Route path="growth" element={<CGrowth />} />
          <Route path="settings" element={<CSettings />} />
        </Route>
        <Route path="e" element={<Guard role="employer"><CabinetLayout role="employer" /></Guard>}>
          <Route index element={<EDashboard />} />
          <Route path="needs" element={<ENeeds />} />
          <Route path="needs/new" element={<ENeedForm />} />
          <Route path="needs/:id/edit" element={<ENeedForm />} />
          <Route path="needs/:id" element={<ENeedDetail />} />
          <Route path="talent" element={<ETalent />} />
          <Route path="candidates/:id" element={<ECandidate />} />
          <Route path="invitations" element={<EInvitations />} />
          <Route path="invitations/:id" element={<EInvitations />} />
          <Route path="vacancies" element={<EVacancies />} />
          <Route path="vacancies/:id" element={<EVacancies />} />
          <Route path="tasks" element={<ETasks />} />
          <Route path="tasks/:id" element={<ETasks />} />
          <Route path="company" element={<ECompany />} />
          <Route path="integrations" element={<EIntegrations />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
