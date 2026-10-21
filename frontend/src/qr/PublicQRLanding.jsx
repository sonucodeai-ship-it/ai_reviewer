import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { qrApi } from "./qrApi";
import { businessSlugify, customerDashboardPath, websitePreviewPath, qrLandingPath } from "./publicUrl";
import "./qr.css";

export default function PublicQRLanding() {
  const { qrToken, businessSlug } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [opening, setOpening] = useState("");

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    setLoading(true);
    qrApi.resolvePublic(qrToken)
      .then((result) => { if (alive) setData(result); })
      .catch((err) => { if (alive) setError(err.message || "This QR code is unavailable."); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [qrToken]);

  // Always canonicalize using the latest saved business name. This also keeps
  // already-printed QR codes working after the owner renames their business.
  useEffect(() => {
    if (!data || !qrToken) return;
    const canonicalPath = qrLandingPath(data.business_name, qrToken);
    if (location.pathname !== canonicalPath || businessSlug !== businessSlugify(data.business_name)) {
      navigate(canonicalPath, { replace: true });
    }
  }, [data, qrToken, businessSlug, location.pathname, navigate]);

  const openDestination = async (type) => {
    if (!data || opening) return;
    setOpening(type);
    try {
      await qrApi.track(qrToken, type === "review" ? "review_click" : "showcase_click");
    } catch (err) {
      // Analytics failures must not block the customer's destination.
      console.warn("QR click analytics could not be recorded:", err);
    }
    if (type === "review") {
      navigate(customerDashboardPath(data.business_name, data.dashboard_public_url_id));
    } else {
      navigate(websitePreviewPath(data.business_name, data.website_public_url_id));
    }
  };

  return <main className="qr-public-page"><section className="qr-public-panel">
    <div className="qr-public-brand"><span>AI</span><strong>AI Reviewer</strong></div>
    {loading ? <div className="qr-state"><span className="qr-spinner" />Opening QR…</div> : error ? <div className="qr-public-error"><div className="qr-public-mark">!</div><h1>QR unavailable</h1><p>{error}</p><p>Please ask the business for an updated QR code.</p></div> : <>
      <div className="qr-public-mark">✓</div>
      <p className="qr-eyebrow">WELCOME</p>
      <h1>{data.business_name || "Welcome"}</h1>
      <p className="qr-public-subtitle">How would you like to continue?</p>
      <div className="qr-public-actions">
        <button type="button" className="qr-public-action qr-public-review" onClick={() => openDestination("review")} disabled={Boolean(opening)}><span className="qr-public-action-icon">★</span><span><strong>Review Us</strong><small>Share your experience with us</small></span><b>→</b></button>
        <button type="button" className="qr-public-action" onClick={() => openDestination("showcase")} disabled={Boolean(opening)}><span className="qr-public-action-icon">⌂</span><span><strong>View Our Digital Showcase</strong><small>Explore our business and services</small></span><b>→</b></button>
      </div>
      {opening && <p className="qr-opening-message">Opening your selection…</p>}
      <p className="qr-public-footer">Powered by AI Reviewer</p>
    </>}
  </section></main>;
}
