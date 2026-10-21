import { useCallback, useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import { qrApi } from "./qrApi";
import { qrLandingPath } from "./publicUrl";
import "./qr.css";

const initialForm = { qr_name: "", dashboard_id: "", website_version_id: "" };

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function downloadBlobUrl(url, filename) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export default function YourQRs() {
  const [qrCodes, setQrCodes] = useState([]);
  const [resources, setResources] = useState({ dashboards: [], website_versions: [], business: {} });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingQR, setEditingQR] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [deletingId, setDeletingId] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [resourceData, qrData] = await Promise.all([qrApi.resources(), qrApi.list()]);
      setResources(resourceData);
      setQrCodes(qrData.qr_codes || []);
    } catch (err) {
      setError(err.message || "Unable to load your QR codes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const websiteOptions = useMemo(() => resources.website_versions || [], [resources.website_versions]);

  const openCreate = () => {
    setEditingQR(null);
    setForm({
      ...initialForm,
      dashboard_id: resources.dashboards?.[0]?.dashboard_id ? String(resources.dashboards[0].dashboard_id) : "",
      website_version_id: websiteOptions[0]?.website_version_id ? String(websiteOptions[0].website_version_id) : "",
    });
    setError("");
    setNotice("");
    setModalOpen(true);
  };

  const openManage = (qr) => {
    setEditingQR(qr);
    setForm({ qr_name: qr.qr_name || "", dashboard_id: String(qr.dashboard_id), website_version_id: String(qr.website_version_id) });
    setError("");
    setNotice("");
    setModalOpen(true);
  };

  const saveQR = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!form.dashboard_id || !form.website_version_id) {
      setError("Choose a review dashboard and a specific showcase version.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        qr_name: form.qr_name.trim(),
        dashboard_id: Number(form.dashboard_id),
        website_version_id: Number(form.website_version_id),
      };
      if (editingQR) {
        await qrApi.update(editingQR.qr_id, payload);
        setNotice("QR configuration updated. Your existing printed QR remains valid.");
      } else {
        await qrApi.create(payload);
        setNotice("QR created successfully. You can download it from its card.");
      }
      setModalOpen(false);
      await loadData();
    } catch (err) {
      setError(err.message || "Unable to save QR configuration.");
    } finally {
      setSaving(false);
    }
  };

  const downloadQR = async (qr) => {
    setDownloadingId(qr.qr_id);
    setError("");
    try {
      // Only the stable public entry URL is embedded. Destinations are resolved by the backend.
      const publicUrl = `${window.location.origin}${qrLandingPath(qr.business_name || resources.business?.business_name, qr.qr_token)}`;
      const dataUrl = await QRCode.toDataURL(publicUrl, {
        errorCorrectionLevel: "H", margin: 3, width: 1024,
        color: { dark: "#101828", light: "#FFFFFF" },
      });
      downloadBlobUrl(dataUrl, `ai-reviewer-qr-${qr.qr_name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || qr.qr_id}.png`);
    } catch (err) {
      setError(err.message || "Unable to download QR image.");
    } finally {
      setDownloadingId(null);
    }
  };

  const toggleStatus = async (qr) => {
    setError("");
    setNotice("");
    try {
      await qrApi.setStatus(qr.qr_id, !qr.is_active);
      setNotice(qr.is_active ? "QR disabled. Its landing page is no longer available." : "QR enabled.");
      await loadData();
    } catch (err) { setError(err.message || "Unable to update QR status."); }
  };

  const deleteQR = async (qr) => {
    const confirmed = window.confirm(`Delete “${qr.qr_name}”? Printed copies will stop working. Analytics history is retained.`);
    if (!confirmed) return;
    setDeletingId(qr.qr_id);
    setError("");
    setNotice("");
    try {
      await qrApi.remove(qr.qr_id);
      setNotice("QR deleted. Existing printed copies will show an unavailable page.");
      await loadData();
    } catch (err) { setError(err.message || "Unable to delete QR."); }
    finally { setDeletingId(null); }
  };

  return (
    <div className="qr-page">
      <div className="qr-page-header">
        <div>
          <div className="qr-eyebrow">AI REVIEWER · CUSTOMER ACCESS</div>
          <h1>Your QR&apos;s</h1>
          <p>Create and manage QR codes that connect customers to your review questionnaire and digital showcase.</p>
        </div>
        <button className="qr-primary-button" type="button" onClick={openCreate}><span aria-hidden="true">＋</span> Create new QR</button>
      </div>

      <div className="qr-free-note"><span className="qr-free-check">✓</span><div><strong>Free to create and download</strong><span>QR codes stay the same when you edit their linked destinations.</span></div></div>

      {error && !modalOpen && <div className="qr-alert qr-alert-error" role="alert">{error}</div>}
      {notice && <div className="qr-alert qr-alert-success" role="status">{notice}<button type="button" onClick={() => setNotice("")} aria-label="Dismiss">×</button></div>}

      {loading ? <div className="qr-state"><span className="qr-spinner" /> Loading your QR codes…</div> : qrCodes.length === 0 ? (
        <div className="qr-empty-state">
          <div className="qr-empty-icon" aria-hidden="true">▦</div>
          <h2>No QR codes yet</h2>
          <p>Create your first QR code and let customers choose between reviewing your business and viewing your digital showcase.</p>
          <button className="qr-primary-button" type="button" onClick={openCreate}>Create your first QR</button>
          {(!resources.dashboards?.length || !websiteOptions.length) && <p className="qr-requirements">You need at least one review dashboard and one saved digital showcase version before creating a QR.</p>}
        </div>
      ) : (
        <div className="qr-card-grid">
          {qrCodes.map((qr) => (
            <article className="qr-card" key={qr.qr_id}>
              <div className="qr-card-top">
                <div className="qr-card-symbol" aria-hidden="true"><svg viewBox="0 0 48 48"><path d="M4 4h15v15H4zM9 9v5h5V9zM29 4h15v15H29zM34 9v5h5V9zM4 29h15v15H4zM9 34v5h5v-5zM25 25h6v6h-6zM35 25h9v5h-9zM25 36h5v8h-5zM34 35h5v4h-5zM41 36h3v8h-3z" fill="currentColor"/></svg></div>
                <span className={`qr-status ${qr.is_active ? "is-active" : "is-disabled"}`}><span />{qr.is_active ? "Active" : "Disabled"}</span>
              </div>
              <h2>{qr.qr_name}</h2>
              <div className="qr-card-date">Created {formatDate(qr.created_at)}</div>
              <div className="qr-destination-list">
                <div><span className="qr-destination-icon">★</span><div><small>Review destination</small><strong>{qr.dashboard_name || "Review dashboard"}</strong></div></div>
                <div><span className="qr-destination-icon">⌂</span><div><small>Digital showcase</small><strong>Version {qr.version_number ?? "—"}</strong></div></div>
              </div>
              <div className="qr-metrics">
                <div><strong>{Number(qr.scans || 0).toLocaleString("en-IN")}</strong><span>Scans</span></div>
                <div><strong>{Number(qr.review_clicks || 0).toLocaleString("en-IN")}</strong><span>Review clicks</span></div>
                <div><strong>{Number(qr.showcase_clicks || 0).toLocaleString("en-IN")}</strong><span>Showcase clicks</span></div>
              </div>
              <div className="qr-card-actions">
                <button className="qr-primary-button qr-download-button" type="button" onClick={() => downloadQR(qr)} disabled={downloadingId === qr.qr_id || !qr.is_active}>
                  {downloadingId === qr.qr_id ? "Preparing…" : "↓ Download PNG"}
                </button>
                <button className="qr-secondary-button" type="button" onClick={() => openManage(qr)}>Manage QR</button>
                <button className="qr-icon-button" type="button" title={qr.is_active ? "Disable QR" : "Enable QR"} aria-label={qr.is_active ? "Disable QR" : "Enable QR"} onClick={() => toggleStatus(qr)}>{qr.is_active ? "Ⅱ" : "▶"}</button>
                <button className="qr-icon-button qr-delete-button" type="button" title="Delete QR" aria-label="Delete QR" disabled={deletingId === qr.qr_id} onClick={() => deleteQR(qr)}>⌫</button>
              </div>
            </article>
          ))}
        </div>
      )}

      {modalOpen && <div className="qr-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) setModalOpen(false); }}>
        <section className="qr-modal" role="dialog" aria-modal="true" aria-labelledby="qr-modal-title">
          <div className="qr-modal-header"><div><div className="qr-eyebrow">QR CONFIGURATION</div><h2 id="qr-modal-title">{editingQR ? "Manage QR" : "Create new QR"}</h2><p>{editingQR ? "Change destinations without changing the printed QR code." : "Choose where customers go after scanning this QR."}</p></div><button type="button" className="qr-modal-close" aria-label="Close" onClick={() => !saving && setModalOpen(false)}>×</button></div>
          <form onSubmit={saveQR}>
            <label className="qr-field"><span>QR name</span><input value={form.qr_name} onChange={(event) => setForm((prev) => ({ ...prev, qr_name: event.target.value }))} placeholder="e.g. Clinic reception" minLength={2} maxLength={120} required /></label>
            <label className="qr-field"><span>Review dashboard</span><select value={form.dashboard_id} onChange={(event) => setForm((prev) => ({ ...prev, dashboard_id: event.target.value }))} required><option value="">Select a dashboard</option>{(resources.dashboards || []).map((item) => <option key={item.dashboard_id} value={item.dashboard_id}>{item.dashboard_name}</option>)}</select></label>
            <label className="qr-field"><span>Digital showcase version</span><select value={form.website_version_id} onChange={(event) => setForm((prev) => ({ ...prev, website_version_id: event.target.value }))} required><option value="">Select a saved version</option>{websiteOptions.map((item) => <option key={item.website_version_id} value={item.website_version_id}>Version {item.version_number} {item.is_active ? "· Current" : ""}</option>)}</select><small>The selected version is pinned. Publishing another version will not change this QR destination.</small></label>
            {error && <div className="qr-alert qr-alert-error" role="alert">{error}</div>}
            <div className="qr-modal-note"><strong>Stable printed QR</strong><span>Editing this setup preserves the same QR token and printed QR image.</span></div>
            <div className="qr-modal-actions"><button className="qr-secondary-button" type="button" onClick={() => setModalOpen(false)} disabled={saving}>Cancel</button><button className="qr-primary-button" type="submit" disabled={saving || !resources.dashboards?.length || !websiteOptions.length}>{saving ? "Saving…" : editingQR ? "Save changes" : "Create QR"}</button></div>
          </form>
        </section>
      </div>}
    </div>
  );
}
