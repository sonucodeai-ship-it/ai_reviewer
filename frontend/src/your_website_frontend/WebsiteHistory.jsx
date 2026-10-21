import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./website_history.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const REQUEST_TIMEOUT_MS = 20000;

function getAuthToken() {
  return localStorage.getItem("access_token");
}

function handleUnauthorized(navigate) {
  localStorage.removeItem("access_token");
  localStorage.removeItem("auth_user");
  navigate("/login", { replace: true });
}

async function requestJson(url, options = {}, fallbackMessage = "Request failed.") {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail =
        typeof data.detail === "string"
          ? data.detail
          : fallbackMessage;
      const error = new Error(detail || fallbackMessage);
      error.status = response.status;
      throw error;
    }

    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        "The server is taking too long to respond. Please check that the backend is running and try again."
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function formatDate(value) {
  if (!value) return "Date unavailable";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function WebsiteHistory() {
  const navigate = useNavigate();

  const [websites, setWebsites] = useState([]);
  const [business, setBusiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadHistory = useCallback(async () => {
    const token = getAuthToken();

    if (!token) {
      handleUnauthorized(navigate);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const data = await requestJson(
        `${API_BASE_URL}/api/your-website/history`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
        "Unable to load website histories."
      );

      setBusiness(data.business || null);
      setWebsites(Array.isArray(data.websites) ? data.websites : []);
    } catch (error) {
      console.error("Website history loading failed:", error);

      if (error?.status === 401) {
        handleUnauthorized(navigate);
        return;
      }

      setError(error.message || "Unable to load website histories.");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const openWebsite = (website) => {
    const publicUrlId = String(website?.public_url_id || "").trim();
    if (!publicUrlId) return;

    navigate(`/your-website/preview/${encodeURIComponent(publicUrlId)}`);
  };

  const openEditor = (event, website) => {
    event.stopPropagation();

    const websiteVersionId = Number(
      website?.website_version_id
    );

    if (
      !Number.isInteger(websiteVersionId) ||
      deletingId !== null ||
      editingId !== null
    ) {
      return;
    }

    setEditingId(websiteVersionId);
    setError("");
    setSuccess("");

    navigate(`/your-website/edit/${websiteVersionId}`);
  };

  const handleDelete = async (event, website) => {
    event.stopPropagation();

    const websiteVersionId = Number(
      website?.website_version_id
    );

    if (
      !Number.isInteger(websiteVersionId) ||
      deletingId !== null
    ) {
      return;
    }

    const versionNumber = Number(
      website?.version_number
    );

    const versionLabel = Number.isInteger(versionNumber)
      ? `V${versionNumber}`
      : "this version";

    const confirmed = window.confirm(
      `Delete ${versionLabel}?\n\nOnly this saved website version will be permanently deleted. Other website versions will remain safe.`
    );

    if (!confirmed) return;

    const token = getAuthToken();

    if (!token) {
      handleUnauthorized(navigate);
      return;
    }

    try {
      setDeletingId(websiteVersionId);
      setError("");
      setSuccess("");

      const data = await requestJson(
        `${API_BASE_URL}/api/your-website/version/${websiteVersionId}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
        "Unable to delete this website version."
      );

      setWebsites((previous) =>
        previous.filter(
          (item) =>
            Number(item.website_version_id) !==
            websiteVersionId
        )
      );

      setSuccess(
        data.message ||
          "Website version deleted successfully."
      );
    } catch (error) {
      console.error(
        "Website version deletion failed:",
        error
      );

      if (error?.status === 401) {
        handleUnauthorized(navigate);
        return;
      }

      setError(
        error.message ||
          "Unable to delete this website version."
      );
    } finally {
      setDeletingId(null);
    }
  };


  if (loading) {
    return (
      <main className="website-history-page">
        <div className="website-history-loading">
          <div className="website-history-spinner" />
          <strong>Loading your website histories</strong>
          <span>Getting your saved website versions...</span>
        </div>
      </main>
    );
  }

  return (
    <main className="website-history-page">
      <div className="website-history-shell">
        <header className="website-history-header">
<div>
            <span className="website-history-kicker">YOUR WEBSITES</span>
            <h1>All Website Histories</h1>
            <p>
              {business?.business_name
                ? `Saved website versions created for ${business.business_name}.`
                : "All of your saved customer-facing website versions."}
            </p>
          </div>

          <button
            type="button"
            className="website-history-create"
            onClick={() => navigate("/your-website")}
          >
            + New Website
          </button>
        </header>

        {error && (
          <div className="website-history-alert" role="alert">
            <strong>Something went wrong</strong>
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="website-history-success" role="status">
            <strong>Deleted</strong>
            <span>{success}</span>
          </div>
        )}

        <section className="website-history-summary">
          <div>
            <span>WEBSITE VERSIONS</span>
            <strong>{websites.length}</strong>
          </div>
          <p>
            Each card represents one generated website version. Opening a card
            loads that exact version using its unique public URL.
          </p>
        </section>

        {websites.length === 0 ? (
          <section className="website-history-empty">
            <div className="website-history-empty-icon">W</div>
            <span className="website-history-kicker">NO WEBSITES YET</span>
            <h2>Create your first website</h2>
            <p>
              Generate a customer-facing website and every generated version
              will appear here automatically.
            </p>
            <button
              type="button"
              className="website-history-primary"
              onClick={() => navigate("/your-website")}
            >
              Create Website <span>→</span>
            </button>
          </section>
        ) : (
          <section className="website-history-grid">
            {websites.map((website, index) => {
              const versionId = Number(
                website.website_version_id
              );
              const isDeleting =
                deletingId === versionId;

              return (
                <article
                  key={versionId || `${website.website_id}-${website.version_number}-${index}`}
                  className={`website-history-card${
                    isDeleting ? " is-deleting" : ""
                  }`}
                  onClick={() => !isDeleting && openWebsite(website)}
                  role="button"
                  tabIndex={isDeleting ? -1 : 0}
                  onKeyDown={(event) => {
                    if (
                      !isDeleting &&
                      (event.key === "Enter" || event.key === " ")
                    ) {
                      event.preventDefault();
                      openWebsite(website);
                    }
                  }}
                  aria-label={`Open website version ${website.version_number || index + 1}`}
                >
                  <div className="website-history-preview-wrap">
                    {website.html_code ? (
                      <iframe
                        title={`Preview of ${website.business_name || "website"} version ${website.version_number || index + 1}`}
                        className="website-history-preview"
                        srcDoc={website.html_code}
                        sandbox="allow-scripts allow-forms allow-popups allow-modals"
                        referrerPolicy="no-referrer"
                        tabIndex={-1}
                      />
                    ) : (
                      <div className="website-history-preview-empty">
                        Preview unavailable
                      </div>
                    )}

                    <div className="website-history-preview-overlay">
                      <span>Open Website</span>
                    </div>

                    <span className="website-history-number">
                      #{String(index + 1).padStart(2, "0")}
                    </span>
                  </div>

                  <div className="website-history-card-body">
                    <div className="website-history-card-top">
                      <div>
                        <span className="website-history-card-label">
                          {website.business_type || "BUSINESS WEBSITE"}
                        </span>
                        <h2>{website.business_name || "Your Website"}</h2>
                      </div>

                      <span className="website-history-version">
                        V{website.version_number || 1}
                      </span>
                    </div>

                    <div className="website-history-meta">
                      <span>
                        {website.created_at
                          ? `Created ${formatDate(website.created_at)}`
                          : "Created date unavailable"}
                      </span>
                    </div>

                    <div className="website-history-actions">
                      <button
                        type="button"
                        className="website-history-open"
                        onClick={(event) => {
                          event.stopPropagation();
                          openWebsite(website);
                        }}
                        disabled={isDeleting || editingId !== null}
                      >
                        View Website <span>→</span>
                      </button>

                      <button
                        type="button"
                        className="website-history-edit"
                        onClick={(event) => openEditor(event, website)}
                        disabled={isDeleting || editingId !== null}
                      >
                        {editingId === versionId ? "Opening..." : "Edit"}
                      </button>

                      <button
                        type="button"
                        className="website-history-delete"
                        onClick={(event) => handleDelete(event, website)}
                        disabled={isDeleting || editingId !== null}
                      >
                        {isDeleting ? "Deleting..." : "Delete Website"}
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}

export default WebsiteHistory;
