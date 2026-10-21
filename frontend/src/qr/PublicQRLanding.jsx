import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { qrApi } from "./qrApi";
import "./qr.css";

export default function PublicQRLanding({ canonicalizeQrLanding, navigateToCustomerDashboard, navigateToWebsitePreview }) {
  const { qrToken } = useParams();
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

  // App.jsx owns canonical URL construction and replacement navigation.
  useEffect(() => {
    if (data && qrToken) canonicalizeQrLanding(data.business_name, qrToken);
  }, [data, qrToken, canonicalizeQrLanding]);

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
      navigateToCustomerDashboard(data.business_name, data.dashboard_public_url_id);
    } else {
      navigateToWebsitePreview(data.business_name, data.website_public_url_id);
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
