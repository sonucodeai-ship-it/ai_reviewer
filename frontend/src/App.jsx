import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/business/:businessId" element={<AdminBusiness />} />
        <Route path="/admin/staff" element={<AdminStaff />} />
        <Route path="/admin/audit-logs" element={<AdminAuditLogs />} />

        {/* -----------------------------------------------------------
            BUSINESS OWNER / AUTHENTICATED APP
            These pages use the shared AppBar shell.
        ------------------------------------------------------------ */}
        <Route element={<AppBar />}>
          <Route path="/menu" element={<Menu />} />
          <Route path="/business-info" element={<BusinessInfo />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/query-maker/:dashboardId" element={<QueryMaker />} />
          <Route path="/google-business" element={<GoogleBusiness />} />
          <Route path="/your-website" element={<YourWebsite />} />
          <Route path="/your-website/history" element={<WebsiteHistory />} />
          <Route
            path="/your-website/edit/:websiteVersionId"
            element={<WebsiteEdit />}
          />
          <Route path="/qr-codes" element={<YourQRs />} />
        </Route>

        {/* -----------------------------------------------------------
            CUSTOMER-FACING PAGES
            These pages intentionally stay outside AppBar.

            ReviewPage is a customer flow, so it must render as a
            clean standalone page without the business-owner navigation.
        ------------------------------------------------------------ */}
        {/* Slugged public customer URLs. Stable tokens/IDs remain the real identifiers. */}
        <Route path="/:businessSlug/:qrToken" element={<PublicQRLanding />} />
        <Route
          path="/:businessSlug/customer-dashboard/:publicUrlId"
          element={<CustomerDashboard />}
        />
        <Route
          path="/:businessSlug/website-preview/:publicUrlId"
          element={<WebsitePreview />}
        />

        {/* Backward-compatible routes: components canonicalize these to slugged URLs. */}
        <Route path="/q/:qrToken" element={<PublicQRLanding />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/customer-dashboard/:publicUrlId" element={<CustomerDashboard />} />
        <Route path="/your-website/preview/:publicUrlId" element={<WebsitePreview />} />

        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
