import { useCallback, useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import Login from "./pages/Login/Login";
import Menu from "./pages/Menu/menu";
import BusinessInfo from "./pages/BusinessInfo/business_info";
import Dashboard from "./pages/Dashboard/dashboard";
import CustomerDashboard from "./pages/CustomerDashboard/customer_dashboard";
import ReviewPage from "./pages/ReviewPage/review_page";
import QueryMaker from "./pages/QueryMaker/query_maker";
import GoogleBusiness from "./ai_review_reply/pages/GoogleBusiness";
import YourWebsite from "./your_website_frontend/YourWebsite";
import WebsiteHistory from "./your_website_frontend/WebsiteHistory";
import WebsitePreview from "./your_website_frontend/WebsitePreview";
import WebsiteEdit from "./your_website_frontend/WebsiteEdit";
import AppBar from "./app_bar/app_bar";
import YourQRs from "./qr/YourQRs";
import PublicQRLanding from "./qr/PublicQRLanding";

import AdminLogin from "./pages/Admin/AdminLogin";
import AdminDashboard from "./pages/Admin/AdminDashboard";
import AdminBusiness from "./pages/Admin/AdminBusiness";
import AdminStaff from "./pages/Admin/AdminStaff";
import AdminAuditLogs from "./pages/Admin/AdminAuditLogs";

const API_BASE_URL = String(
  import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_BACKEND_URL ||
    "http://127.0.0.1:8000"
).replace(/\/$/, "");

/* All canonical public URL rules are intentionally kept in App.jsx. */
function businessSlugify(value) {
  const slug = String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80)
    .replace(/-+$/g, "");

  return slug || "business";
}

function customerDashboardPath(businessName, publicUrlId) {
  return `/${businessSlugify(businessName)}/customer-dashboard/${encodeURIComponent(String(publicUrlId || ""))}`;
}

function websitePreviewPath(businessName, publicUrlId) {
  return `/${businessSlugify(businessName)}/website-preview/${encodeURIComponent(String(publicUrlId || ""))}`;
}

function qrLandingPath(businessName, qrToken) {
  return `/${businessSlugify(businessName)}/${encodeURIComponent(String(qrToken || ""))}`;
}

function RedirectLoading({ message = "Opening page…" }) {
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <p role="status">{message}</p>
    </main>
  );
}

function RedirectError({ message }) {
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <section style={{ maxWidth: 480 }}>
        <h1>Page unavailable</h1>
        <p role="alert">{message}</p>
      </section>
    </main>
  );
}

/* Old public URLs are resolved here, before mounting the destination page. */
function LegacyCustomerDashboardRedirect() {
  const { publicUrlId } = useParams();
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function resolveUrl() {
      if (!publicUrlId) {
        setError("This customer dashboard link is incomplete.");
        return;
      }
      try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/public/${encodeURIComponent(publicUrlId)}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to resolve this customer dashboard link.");
        if (active) setTarget(customerDashboardPath(data.dashboard?.business_name || "Your Business", publicUrlId));
      } catch (err) {
        if (active) setError(err.message || "Unable to resolve this customer dashboard link.");
      }
    }
    resolveUrl();
    return () => { active = false; };
  }, [publicUrlId]);

  if (target) return <Navigate to={target} replace />;
  if (error) return <RedirectError message={error} />;
  return <RedirectLoading message="Opening customer dashboard…" />;
}

function LegacyWebsitePreviewRedirect() {
  const { publicUrlId } = useParams();
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function resolveUrl() {
      if (!publicUrlId) {
        setError("This website preview link is incomplete.");
        return;
      }
      try {
        const response = await fetch(`${API_BASE_URL}/api/your-website/public/${encodeURIComponent(publicUrlId)}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to resolve this website preview link.");
        if (active) setTarget(websitePreviewPath(data.business?.business_name || "Your Business", publicUrlId));
      } catch (err) {
        if (active) setError(err.message || "Unable to resolve this website preview link.");
      }
    }
    resolveUrl();
    return () => { active = false; };
  }, [publicUrlId]);

  if (target) return <Navigate to={target} replace />;
  if (error) return <RedirectError message={error} />;
  return <RedirectLoading message="Opening website preview…" />;
}


/* Resolve the current business name before mounting public pages. This keeps
   slug canonicalization in App.jsx and avoids a page-level remount/empty flash. */
function CanonicalCustomerDashboardRoute({ navigateToReview, navigateToQueryMaker }) {
  const { businessSlug, publicUrlId } = useParams();
  const [target, setTarget] = useState("");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function resolve() {
      setReady(false);
      setTarget("");
      setError("");
      try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/public/${encodeURIComponent(publicUrlId || "")}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to load this customer dashboard.");
        const targetPath = customerDashboardPath(data.dashboard?.business_name || "Your Business", publicUrlId);
        if (!active) return;
        if (targetPath !== window.location.pathname) setTarget(targetPath);
        else setReady(true);
      } catch (err) {
        if (active) setError(err.message || "Unable to load this customer dashboard.");
      }
    }
    resolve();
    return () => { active = false; };
  }, [businessSlug, publicUrlId]);

  if (target) return <Navigate to={target} replace />;
  if (error) return <RedirectError message={error} />;
  if (!ready) return <RedirectLoading message="Opening customer dashboard…" />;
  return <CustomerDashboard navigateToReview={navigateToReview} navigateToQueryMaker={navigateToQueryMaker} />;
}

function CanonicalWebsitePreviewRoute() {
  const { businessSlug, publicUrlId } = useParams();
  const [target, setTarget] = useState("");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function resolve() {
      setReady(false);
      setTarget("");
      setError("");
      try {
        const response = await fetch(`${API_BASE_URL}/api/your-website/public/${encodeURIComponent(publicUrlId || "")}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to load this website preview.");
        const targetPath = websitePreviewPath(data.business?.business_name || "Your Business", publicUrlId);
        if (!active) return;
        if (targetPath !== window.location.pathname) setTarget(targetPath);
        else setReady(true);
      } catch (err) {
        if (active) setError(err.message || "Unable to load this website preview.");
      }
    }
    resolve();
    return () => { active = false; };
  }, [businessSlug, publicUrlId]);

  if (target) return <Navigate to={target} replace />;
  if (error) return <RedirectError message={error} />;
  if (!ready) return <RedirectLoading message="Opening website preview…" />;
  return <WebsitePreview />;
}

function AppRoutes() {
  const navigate = useNavigate();
  const location = useLocation();

  const navigateToCustomerDashboard = useCallback((businessName, publicUrlId, options) => {
    if (!publicUrlId) return;
    navigate(customerDashboardPath(businessName, publicUrlId), options);
  }, [navigate]);

  const navigateToWebsitePreview = useCallback((businessName, publicUrlId, options) => {
    if (!publicUrlId) return;
    navigate(websitePreviewPath(businessName, publicUrlId), options);
  }, [navigate]);

  const navigateToReview = useCallback((state) => {
    navigate("/review", { state });
  }, [navigate]);

  const navigateToQueryMaker = useCallback((dashboardId) => {
    if (!dashboardId) return;
    navigate(`/query-maker/${encodeURIComponent(String(dashboardId))}`);
  }, [navigate]);

  const canonicalizeQrLanding = useCallback((businessName, qrToken) => {
    if (!qrToken) return;
    const target = qrLandingPath(businessName, qrToken);
    if (location.pathname !== target) navigate(target, { replace: true });
  }, [location.pathname, navigate]);

  const getQrLandingUrl = useCallback((businessName, qrToken) => {
    return `${window.location.origin}${qrLandingPath(businessName, qrToken)}`;
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      {/* Admin pages */}
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/admin/business/:businessId" element={<AdminBusiness />} />
      <Route path="/admin/staff" element={<AdminStaff />} />
      <Route path="/admin/audit-logs" element={<AdminAuditLogs />} />

      {/* Business-owner pages */}
      <Route element={<AppBar />}>
        <Route path="/menu" element={<Menu />} />
        <Route path="/business-info" element={<BusinessInfo />} />
        <Route path="/dashboard" element={<Dashboard navigateToCustomerDashboard={navigateToCustomerDashboard} />} />
        <Route path="/query-maker/:dashboardId" element={<QueryMaker />} />
        <Route path="/google-business" element={<GoogleBusiness />} />
        <Route path="/your-website" element={<YourWebsite />} />
        <Route path="/your-website/history" element={<WebsiteHistory />} />
        <Route path="/your-website/edit/:websiteVersionId" element={<WebsiteEdit />} />
        <Route path="/qr-codes" element={<YourQRs getQrLandingUrl={getQrLandingUrl} />} />
      </Route>

      {/* Canonical customer-facing URLs */}
      <Route
        path="/:businessSlug/customer-dashboard/:publicUrlId"
        element={<CanonicalCustomerDashboardRoute navigateToReview={navigateToReview} navigateToQueryMaker={navigateToQueryMaker} />}
      />
      <Route path="/:businessSlug/website-preview/:publicUrlId" element={<CanonicalWebsitePreviewRoute />} />

      {/* Public QR landing: both canonical and older QR formats remain valid. */}
      <Route
        path="/:businessSlug/:qrToken"
        element={
          <PublicQRLanding
            canonicalizeQrLanding={canonicalizeQrLanding}
            navigateToCustomerDashboard={navigateToCustomerDashboard}
            navigateToWebsitePreview={navigateToWebsitePreview}
          />
        }
      />
      <Route
        path="/q/:qrToken"
        element={
          <PublicQRLanding
            canonicalizeQrLanding={canonicalizeQrLanding}
            navigateToCustomerDashboard={navigateToCustomerDashboard}
            navigateToWebsitePreview={navigateToWebsitePreview}
          />
        }
      />

      {/* Legacy URLs are redirected centrally, not from destination components. */}
      <Route path="/customer-dashboard/:publicUrlId" element={<LegacyCustomerDashboardRedirect />} />
      <Route path="/your-website/preview/:publicUrlId" element={<LegacyWebsitePreviewRedirect />} />
      <Route path="/review" element={<ReviewPage />} />

      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
