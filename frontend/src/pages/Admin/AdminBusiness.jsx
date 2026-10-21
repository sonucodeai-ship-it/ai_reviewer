import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import "./AdminBusiness.css";

/*
 * Admin API configuration.
 *
 * VITE_PUBLIC_APP_URL is optional.
 * If it is not configured, the current browser origin is used.
 *
 * Example:
 * VITE_PUBLIC_APP_URL=https://ai-reviewer-0ssx.onrender.com
 */
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_BACKEND_URL ||
  "http://127.0.0.1:8000";

const PUBLIC_APP_URL =
  import.meta.env.VITE_PUBLIC_APP_URL ||
  window.location.origin;

const ADMIN_TOKEN_KEY = "admin_access_token";

const formatDateTime = (value) => {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
};

const buildPublicUrl = (path, publicUrlId) => {
  const id = String(publicUrlId || "").trim();

  if (!id || id === "undefined" || id === "null") {
    throw new Error("This public URL is not available.");
  }

  const base = PUBLIC_APP_URL.replace(/\/+$/, "");

  return `${base}${path}/${encodeURIComponent(id)}`;
};

function openPublicPage(path, publicUrlId, label) {
  const url = buildPublicUrl(path, publicUrlId);

  /*
   * window.open is intentionally used here because the View action
   * must open the real customer-facing experience in a separate tab.
   */
  const opened = window.open(
    url,
    "_blank",
    "noopener,noreferrer"
  );

  if (!opened) {
    throw new Error(
      `The browser blocked the ${label} window. Please allow pop-ups for this site.`
    );
  }
}

export default function AdminBusiness() {
  const { businessId } = useParams();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [tab, setTab] = useState("overview");

  const [dashboardDetail, setDashboardDetail] = useState(null);
  const [queryDetail, setQueryDetail] = useState(null);

  const [websiteVersions, setWebsiteVersions] = useState([]);
  const [websiteVersion, setWebsiteVersion] = useState(null);

  const [google, setGoogle] = useState(null);
  const [coinBalance, setCoinBalance] = useState(null);
  const [edit, setEdit] = useState(null);

  const [message, setMessage] = useState("");
  const [coinGrant, setCoinGrant] = useState("");
  const [saving, setSaving] = useState(false);

  const apiFetch = useCallback(
    async (url, options = {}) => {
      const token = localStorage.getItem(ADMIN_TOKEN_KEY);

      if (!token) {
        navigate("/admin/login", { replace: true });
        throw new Error("Admin session expired.");
      }

      const response = await fetch(url, {
        ...options,
        headers: {
          ...(options.headers || {}),
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.status === 401) {
        localStorage.removeItem(ADMIN_TOKEN_KEY);
        localStorage.removeItem("admin_profile");

        navigate("/admin/login", { replace: true });

        throw new Error("Admin session expired.");
      }

      return response;
    },
    [navigate]
  );

  const loadBusiness = useCallback(async () => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/admin/businesses/${businessId}`
    );

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(
        payload.detail || "Unable to load business."
      );
    }

    setData(payload);

    try {
      const coinResponse = await apiFetch(
        `${API_BASE_URL}/api/admin/businesses/${businessId}/coins`
      );

      const coinPayload = await coinResponse.json();

      if (coinResponse.ok) {
        setCoinBalance(coinPayload);
      }
    } catch (error) {
      console.error("Coin balance loading failed:", error);
    }
  }, [apiFetch, businessId]);

  useEffect(() => {
    loadBusiness().catch((error) => {
      setMessage(error.message);
    });
  }, [loadBusiness]);

  const grantCoins = async () => {
    const coins = Number(coinGrant);

    if (!Number.isInteger(coins) || coins <= 0) {
      setMessage("Enter a valid positive coin amount.");
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/admin/businesses/${businessId}/coins/grant`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ coins }),
        }
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail || "Unable to grant coins."
        );
      }

      setCoinBalance(payload);
      setCoinGrant("");
      setMessage(
        `${coins.toLocaleString("en-IN")} coins granted successfully.`
      );
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSaving(false);
    }
  };

  const save = async (url, body, successMessage) => {
    setSaving(true);
    setMessage("");

    try {
      const response = await apiFetch(url, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail || "Unable to save changes."
        );
      }

      setEdit(null);
      setMessage(successMessage);

      await loadBusiness();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSaving(false);
    }
  };

  const openDashboardWorkspace = async (dashboardId) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/admin/businesses/${businessId}/dashboards/${dashboardId}`
    );

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(
        payload.detail || "Unable to load dashboard."
      );
    }

    setDashboardDetail(payload);
    setTab("dashboard");
  };

  const openQuery = async (queryId) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/admin/businesses/${businessId}/queries/${queryId}`
    );

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(
        payload.detail || "Unable to load question."
      );
    }

    setQueryDetail(payload);
    setTab("query");
  };

  const openWebsites = async () => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/admin/businesses/${businessId}/websites`
    );

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(
        payload.detail || "Unable to load websites."
      );
    }

    setWebsiteVersions(payload.versions || []);
    setWebsiteVersion(null);
    setTab("websites");
  };

  const openWebsiteEditor = async (versionId) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/admin/businesses/${businessId}/websites/versions/${versionId}`
    );

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(
        payload.detail || "Unable to load website version."
      );
    }

    setWebsiteVersion(payload.version);
  };

  const openGoogle = async () => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/admin/businesses/${businessId}/google`
    );

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(
        payload.detail || "Unable to load Google connection."
      );
    }

    setGoogle(payload.google);
    setTab("google");
  };

  const viewDashboard = (publicUrlId) => {
    try {
      openPublicPage(
        "/customer-dashboard",
        publicUrlId,
        "dashboard"
      );
    } catch (error) {
      setMessage(error.message);
    }
  };

  const viewWebsite = (publicUrlId) => {
    try {
      openPublicPage(
        "/your-website/preview",
        publicUrlId,
        "website"
      );
    } catch (error) {
      setMessage(error.message);
    }
  };

  if (!data) {
    return (
      <main className="ab-load">
        Loading business workspace...
      </main>
    );
  }

  const business = data.business;

  return (
    <main className="ab">
      <header className="ab-head">
        <button
          type="button"
          onClick={() => navigate("/admin")}
        >
          ← Businesses
        </button>

        <div className="ab-title">
          <span>
            {(business.business_name || "B")[0]}
          </span>

          <div>
            <small>BUSINESS WORKSPACE</small>

            <h1>{business.business_name}</h1>

            <p>
              {business.business_type || "Business"} ·{" "}
              {business.email}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setEdit({ ...business })}
        >
          Edit business
        </button>
      </header>

      {message && (
        <div className="ab-msg">
          {message}
        </div>
      )}

      <nav className="ab-tabs">
        {[
          ["overview", "Overview"],
          ["dashboards", "Dashboards"],
          ["websites", "Websites"],
          ["google", "Google"],
          ["account", "Account"],
        ].map(([key, label]) => (
          <button
            type="button"
            key={key}
            className={tab === key ? "active" : ""}
            onClick={() => {
              if (key === "websites") {
                openWebsites().catch((error) =>
                  setMessage(error.message)
                );
                return;
              }

              if (key === "google") {
                openGoogle().catch((error) =>
                  setMessage(error.message)
                );
                return;
              }

              setTab(key);
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* =========================================================
          OVERVIEW
          ========================================================= */}

      {tab === "overview" && (
        <div className="ab-grid">
          <section className="ab-card">
            <small>BUSINESS INFORMATION</small>

            <h2>Profile</h2>

            <div className="ab-info">
              {[
                ["Business name", business.business_name],
                ["Type", business.business_type],
                ["Year", business.year_established],
                ["Owner email", business.email],
                ["Mobile", business.mobile],
                ["Reviews", data.review_count],
              ].map(([label, value]) => (
                <div key={label}>
                  <small>{label}</small>
                  <b>{value || "—"}</b>
                </div>
              ))}
            </div>

            <hr />

            <small>ABOUT</small>

            <p>
              {business.about_business ||
                "No description provided."}
            </p>
          </section>

          <section className="ab-card ab-coin-card">
            <small>COIN BALANCE</small>

            <div className="ab-coin-summary">
              <div>
                <span>Current balance</span>
                <strong>
                  {Number(
                    coinBalance?.coin_balance || 0
                  ).toLocaleString("en-IN")}
                </strong>
                <small>
                  Last updated{" "}
                  {formatDateTime(
                    coinBalance?.updates_at
                  )}
                </small>
              </div>

              <span className="ab-coin-symbol">C</span>
            </div>

            <div className="ab-coin-grant">
              <input
                type="number"
                min="1"
                step="1"
                value={coinGrant}
                onChange={(event) =>
                  setCoinGrant(event.target.value)
                }
                placeholder="Coins to grant"
              />

              <button
                type="button"
                className="primary"
                disabled={saving}
                onClick={grantCoins}
              >
                {saving ? "Granting..." : "Grant coins"}
              </button>
            </div>

            <p className="security">
              Only Super Admin can grant coins. Every grant is
              recorded in the coin balance history and admin audit log.
            </p>
          </section>

          <section className="ab-card">
            <small>PRODUCT</small>

            <h2>Workspace</h2>

            <button
              type="button"
              className="ab-link"
              onClick={() => setTab("dashboards")}
            >
              <b>{data.dashboards.length}</b>
              <span>Published dashboards</span>
              <span>→</span>
            </button>

            <button
              type="button"
              className="ab-link"
              onClick={openWebsites}
            >
              <b>
                {data.websites.reduce(
                  (total, website) =>
                    total + website.versions,
                  0
                )}
              </b>
              <span>Website versions</span>
              <span>→</span>
            </button>

            <button
              type="button"
              className="ab-link"
              onClick={openGoogle}
            >
              <b>G</b>
              <span>Google Business Profile</span>
              <span>→</span>
            </button>
          </section>
        </div>
      )}

      {/* =========================================================
          DASHBOARDS
          ========================================================= */}

      {tab === "dashboards" && (
        <section className="ab-card">
          <small>REVIEW EXPERIENCE</small>

          <div className="ab-section-head">
            <div>
              <h2>Published dashboards</h2>
              <p>
                View the exact customer-facing dashboard or
                manage its configuration.
              </p>
            </div>
          </div>

          <div className="ab-list">
            {data.dashboards.length === 0 ? (
              <div className="ab-empty">
                No dashboards found.
              </div>
            ) : (
              data.dashboards.map((dashboard) => (
                <article
                  key={dashboard.dashboard_id}
                  className="ab-resource"
                >
                  <div className="ab-resource-main">
                    <b>{dashboard.dashboard_name}</b>

                    <small>
                      Published customer dashboard ·{" "}
                      {formatDateTime(
                        dashboard.updated_at
                      )}
                    </small>

                    <code>
                      {dashboard.public_url_id}
                    </code>
                  </div>

                  <div className="ab-actions">
                    <button
                      type="button"
                      className="ab-view-button"
                      onClick={() =>
                        viewDashboard(
                          dashboard.public_url_id
                        )
                      }
                    >
                      View
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        openDashboardWorkspace(
                          dashboard.dashboard_id
                        ).catch((error) =>
                          setMessage(error.message)
                        )
                      }
                    >
                      Manage
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      )}

      {/* =========================================================
          DASHBOARD WORKSPACE
          ========================================================= */}

      {tab === "dashboard" && dashboardDetail && (
        <section className="ab-card">
          <button
            type="button"
            className="plain"
            onClick={() => setTab("dashboards")}
          >
            ← Dashboards
          </button>

          <div className="ab-detail-head">
            <div>
              <small>PUBLISHED CUSTOMER DASHBOARD</small>

              <h2>
                {dashboardDetail.dashboard.dashboard_name}
              </h2>
            </div>

            <div className="ab-actions">
              <button
                type="button"
                className="ab-view-button"
                onClick={() =>
                  viewDashboard(
                    dashboardDetail.dashboard.public_url_id
                  )
                }
              >
                View dashboard
              </button>

              <button
                type="button"
                onClick={() =>
                  setEdit({
                    ...dashboardDetail.dashboard,
                  })
                }
              >
                Edit name
              </button>
            </div>
          </div>

          <div className="ab-list">
            {dashboardDetail.queries.map((query) => (
              <article key={query.query_id}>
                <div>
                  <b>{query.query_text}</b>
                  <small>
                    {query.option_count} options
                  </small>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    openQuery(query.query_id).catch(
                      (error) =>
                        setMessage(error.message)
                    )
                  }
                >
                  Manage
                </button>
              </article>
            ))}
          </div>

          <h3 className="ab-subheading">
            Generated reviews
          </h3>

          <div className="ab-reviews">
            {dashboardDetail.reviews.map((review) => (
              <article key={review.review_id}>
                <p>{review.review_text}</p>

                <small>
                  Google hand-off:{" "}
                  {review.submit_status
                    ? "Opened"
                    : "Not opened"}
                </small>

                <button
                  type="button"
                  onClick={() => setEdit(review)}
                >
                  Edit
                </button>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* =========================================================
          QUESTION
          ========================================================= */}

      {tab === "query" && queryDetail && (
        <section className="ab-card">
          <button
            type="button"
            className="plain"
            onClick={() => setTab("dashboard")}
          >
            ← Dashboard
          </button>

          <div className="ab-detail-head">
            <div>
              <small>QUESTION</small>

              <h2>{queryDetail.query.query_text}</h2>
            </div>

            <button
              type="button"
              onClick={() =>
                setEdit({ ...queryDetail.query })
              }
            >
              Edit
            </button>
          </div>

          <div className="ab-list">
            {queryDetail.options.map((option) => (
              <article key={option.option_id}>
                <b>{option.option_text}</b>

                <button
                  type="button"
                  onClick={() => setEdit(option)}
                >
                  Edit
                </button>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* =========================================================
          WEBSITES
          ========================================================= */}

      {tab === "websites" && (
        <section className="ab-card">
          <small>OWNER WEBSITE</small>

          <div className="ab-section-head">
            <div>
              <h2>Website versions</h2>

              <p>
                View the exact customer-facing website
                version or edit its stored HTML.
              </p>
            </div>
          </div>

          <div className="ab-version-grid">
            {websiteVersions.length === 0 ? (
              <div className="ab-empty">
                No website versions found.
              </div>
            ) : (
              websiteVersions.map((version) => (
                <article
                  key={version.website_version_id}
                  className="ab-version-card"
                >
                  <div className="ab-version-top">
                    <b>V{version.version_number}</b>
                  </div>

                  <small>
                    Created{" "}
                    {formatDateTime(
                      version.created_at
                    )}
                  </small>

                  <code>
                    {version.public_url_id}
                  </code>

                  <div className="ab-actions ab-actions-stack">
                    <button
                      type="button"
                      className="ab-view-button"
                      onClick={() =>
                        viewWebsite(
                          version.public_url_id
                        )
                      }
                    >
                      View website
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        openWebsiteEditor(
                          version.website_version_id
                        ).catch((error) =>
                          setMessage(error.message)
                        )
                      }
                    >
                      Edit
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>

          {websiteVersion && (
            <div className="ab-editor">
              <div className="ab-detail-head">
                <div>
                  <small>WEBSITE VERSION</small>
                  <h3>
                    V{websiteVersion.version_number}
                  </h3>
                </div>

                <div className="ab-actions">
                  <button
                    type="button"
                    className="ab-view-button"
                    onClick={() =>
                      viewWebsite(
                        websiteVersion.public_url_id
                      )
                    }
                  >
                    View website
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setWebsiteVersion(null)
                    }
                  >
                    Close
                  </button>
                </div>
              </div>

              <textarea
                value={websiteVersion.html_code || ""}
                onChange={(event) =>
                  setWebsiteVersion({
                    ...websiteVersion,
                    html_code: event.target.value,
                  })
                }
              />

              <div className="ab-two">
                <input
                  value={
                    websiteVersion.color_theme_1 || ""
                  }
                  onChange={(event) =>
                    setWebsiteVersion({
                      ...websiteVersion,
                      color_theme_1:
                        event.target.value,
                    })
                  }
                  placeholder="Theme 1"
                />

                <input
                  value={
                    websiteVersion.color_theme_2 || ""
                  }
                  onChange={(event) =>
                    setWebsiteVersion({
                      ...websiteVersion,
                      color_theme_2:
                        event.target.value,
                    })
                  }
                  placeholder="Theme 2"
                />
              </div>

              <button
                type="button"
                className="primary"
                disabled={saving}
                onClick={() =>
                  save(
                    `${API_BASE_URL}/api/admin/businesses/${businessId}/websites/versions/${websiteVersion.website_version_id}`,
                    {
                      html_code:
                        websiteVersion.html_code,
                      color_theme_1:
                        websiteVersion.color_theme_1 ||
                        null,
                      color_theme_2:
                        websiteVersion.color_theme_2 ||
                        null,
                    },
                    "Website version updated."
                  )
                }
              >
                {saving
                  ? "Saving..."
                  : "Save website changes"}
              </button>
            </div>
          )}
        </section>
      )}

      {/* =========================================================
          GOOGLE
          ========================================================= */}

      {tab === "google" && (
        <section className="ab-card">
          <small>GOOGLE BUSINESS PROFILE</small>

          <h2>Connection</h2>

          {google ? (
            <div className="ab-google">
              {[
                ["Status", google.connection_status],
                [
                  "Account",
                  google.google_account_name,
                ],
                [
                  "Location",
                  google.google_location_title ||
                    google.google_location_id,
                ],
                ["Updated", formatDateTime(google.updated_at)],
              ].map(([label, value]) => (
                <div key={label}>
                  <small>{label}</small>
                  <b>{value || "—"}</b>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty">
              No Google Business Profile connection.
            </p>
          )}

          <p className="security">
            Tokens are intentionally never exposed in
            the admin interface.
          </p>
        </section>
      )}

      {/* =========================================================
          OWNER ACCOUNT
          ========================================================= */}

      {tab === "account" && (
        <section className="ab-card">
          <small>OWNER ACCOUNT</small>

          <h2>Account</h2>

          <div className="account">
            <b>{business.email}</b>
            <span>
              {business.mobile ||
                "No mobile number"}
            </span>

            <em
              className={
                business.user_is_active
                  ? "active"
                  : "inactive"
              }
            >
              {business.user_is_active
                ? "Active"
                : "Inactive"}
            </em>
          </div>
        </section>
      )}

      {/* =========================================================
          EDIT MODAL
          ========================================================= */}

      {edit && (
        <Modal
          title={
            edit.dashboard_id
              ? "Edit dashboard"
              : edit.query_id
                ? "Edit question"
                : edit.option_id
                  ? "Edit option"
                  : edit.review_id
                    ? "Edit review"
                    : "Edit business"
          }
          close={() => setEdit(null)}
        >
          {edit.dashboard_id ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();

                save(
                  `${API_BASE_URL}/api/admin/businesses/${businessId}/dashboards/${edit.dashboard_id}`,
                  {
                    dashboard_name:
                      edit.dashboard_name,
                  },
                  "Dashboard updated."
                );
              }}
            >
              <label>
                Name

                <input
                  required
                  value={edit.dashboard_name}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      dashboard_name:
                        event.target.value,
                    })
                  }
                />
              </label>

              <button
                type="submit"
                className="primary"
              >
                Save
              </button>
            </form>
          ) : edit.query_id ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();

                save(
                  `${API_BASE_URL}/api/admin/businesses/${businessId}/queries/${edit.query_id}`,
                  {
                    query_text:
                      edit.query_text,
                  },
                  "Question updated."
                );
              }}
            >
              <label>
                Question

                <textarea
                  value={edit.query_text}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      query_text:
                        event.target.value,
                    })
                  }
                />
              </label>

              <button
                type="submit"
                className="primary"
              >
                Save
              </button>
            </form>
          ) : edit.option_id ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();

                save(
                  `${API_BASE_URL}/api/admin/businesses/${businessId}/options/${edit.option_id}`,
                  {
                    option_text:
                      edit.option_text,
                  },
                  "Option updated."
                );
              }}
            >
              <label>
                Option

                <textarea
                  value={edit.option_text}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      option_text:
                        event.target.value,
                    })
                  }
                />
              </label>

              <button
                type="submit"
                className="primary"
              >
                Save
              </button>
            </form>
          ) : edit.review_id ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();

                save(
                  `${API_BASE_URL}/api/admin/businesses/${businessId}/reviews/${edit.review_id}`,
                  {
                    review_text:
                      edit.review_text,
                    submit_status:
                      Number(edit.submit_status),
                  },
                  "Review updated."
                );
              }}
            >
              <label>
                Review

                <textarea
                  value={edit.review_text}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      review_text:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Status

                <select
                  value={edit.submit_status}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      submit_status:
                        Number(
                          event.target.value
                        ),
                    })
                  }
                >
                  <option value={0}>
                    Not opened
                  </option>
                  <option value={1}>
                    Opened
                  </option>
                </select>
              </label>

              <button
                type="submit"
                className="primary"
              >
                Save
              </button>
            </form>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();

                save(
                  `${API_BASE_URL}/api/admin/businesses/${businessId}`,
                  {
                    business_name:
                      edit.business_name,
                    business_type:
                      edit.business_type || null,
                    about_business:
                      edit.about_business || null,
                    year_established:
                      edit.year_established
                        ? Number(
                            edit.year_established
                          )
                        : null,
                    email: edit.email,
                    mobile:
                      edit.mobile || null,
                    user_is_active:
                      edit.user_is_active,
                  },
                  "Business updated."
                );
              }}
            >
              <label>
                Name

                <input
                  value={edit.business_name}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      business_name:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Type

                <input
                  value={edit.business_type || ""}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      business_type:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Year

                <input
                  type="number"
                  value={
                    edit.year_established || ""
                  }
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      year_established:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Email

                <input
                  type="email"
                  value={edit.email}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      email:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Mobile

                <input
                  value={edit.mobile || ""}
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      mobile:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                About

                <textarea
                  value={
                    edit.about_business || ""
                  }
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      about_business:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label className="ab-check">
                <input
                  type="checkbox"
                  checked={
                    Boolean(edit.user_is_active)
                  }
                  onChange={(event) =>
                    setEdit({
                      ...edit,
                      user_is_active:
                        event.target.checked,
                    })
                  }
                />

                Owner active
              </label>

              <button
                type="submit"
                className="primary"
              >
                Save
              </button>
            </form>
          )}
        </Modal>
      )}
    </main>
  );
}

function Modal({ title, close, children }) {
  return (
    <div
      className="ab-modal-bg"
      onMouseDown={close}
    >
      <section
        className="ab-modal"
        onMouseDown={(event) =>
          event.stopPropagation()
        }
      >
        <header>
          <h2>{title}</h2>

          <button
            type="button"
            onClick={close}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        {children}
      </section>
    </div>
  );
}
