import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import "../styles/google_business.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

async function apiFetch(url, options = {}) {
  const token = localStorage.getItem("access_token");

  if (!token) {
    throw new Error("Your session has expired. Please log in again.");
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (response.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("auth_user");
    window.location.href = "/login";
    throw new Error("Your session has expired.");
  }

  if (!response.ok) {
    throw new Error(data.detail || "Unable to complete the request.");
  }

  return data;
}

export default function GoogleBusiness() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [business, setBusiness] = useState(null);
  const [connection, setConnection] = useState(null);
  const [connected, setConnected] = useState(false);
  const [locations, setLocations] = useState([]);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");

  const showMessage = (text, type = "error") => {
    setMessage(text);
    setMessageType(type);
  };

  const loadStatus = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch(
        `${API_BASE_URL}/api/ai-review-reply/google/status`
      );
      setBusiness(data.business || null);
      setConnection(data.connection || null);
      setConnected(Boolean(data.connected));
    } catch (error) {
      console.error("Google connection status error:", error);
      showMessage(error.message || "Unable to load Google connection.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadLocations = useCallback(async () => {
    try {
      const data = await apiFetch(
        `${API_BASE_URL}/api/ai-review-reply/google/locations`
      );
      setLocations(data.locations || []);
    } catch (error) {
      console.error("Google locations error:", error);
      showMessage(error.message || "Unable to load Google locations.");
    }
  }, []);

  useEffect(() => {
    const status = searchParams.get("google_oauth");
    if (status === "success") {
      showMessage(
        "Google account connected. Select the business location to finish setup.",
        "success"
      );
    } else if (status === "denied") {
      showMessage("Google authorization was cancelled.");
    } else if (status === "failed") {
      showMessage("Google authorization could not be completed. Please try again.");
    }
    loadStatus();
  }, [loadStatus, searchParams]);

  useEffect(() => {
    if (connection?.google_account_name && !connection?.google_location_id) {
      loadLocations();
    }
  }, [connection?.google_account_name, connection?.google_location_id, loadLocations]);

  const handleConnect = async () => {
    setConnecting(true);
    setMessage("");
    try {
      const data = await apiFetch(
        `${API_BASE_URL}/api/ai-review-reply/google/connect`
      );
      if (!data.authorization_url) {
        throw new Error("Google authorization URL was not returned.");
      }
      window.location.assign(data.authorization_url);
    } catch (error) {
      console.error("Google connection start error:", error);
      showMessage(error.message || "Unable to start Google authorization.");
      setConnecting(false);
    }
  };

  const handleSelectLocation = async (locationName) => {
    setSelecting(true);
    setMessage("");
    try {
      const data = await apiFetch(
        `${API_BASE_URL}/api/ai-review-reply/google/select-location`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ location_name: locationName }),
        }
      );
      showMessage(
        data.message || "Google Business Profile connected successfully.",
        "success"
      );
      await loadStatus();
    } catch (error) {
      console.error("Google location selection error:", error);
      showMessage(error.message || "Unable to connect this location.");
    } finally {
      setSelecting(false);
    }
  };

  if (loading) {
    return (
      <main className="google-business-page">
        <div className="google-business-shell google-business-loading">
          <div className="google-business-spinner" />
          <p>Loading Google Business connection...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="google-business-page">
      <div className="google-business-shell">
        <header className="google-business-header">
          <button
            type="button"
            className="google-business-back"
            onClick={() => navigate("/menu")}
          >
            ← Back
          </button>

          <span className="google-business-eyebrow">AI REVIEW REPLY</span>
          <h1>Google Business Profile</h1>
          <p>
            Connect your Google Business Profile to manage customer reviews
            and replies from AI Reviewer.
          </p>
        </header>

        {message && (
          <div className={`google-business-message ${messageType}`} role="status">
            {message}
          </div>
        )}

        <section className="google-business-card">
          <div className="google-business-card-top">
            <div className="google-business-google-mark">G</div>
            <div>
              <span className="google-business-label">BUSINESS CONNECTION</span>
              <h2>{business?.business_name || "Your Business"}</h2>
            </div>
            <span className={`google-business-status ${connected ? "connected" : "not-connected"}`}>
              <span />
              {connected ? "Connected" : "Not connected"}
            </span>
          </div>

          {connected ? (
            <>
              <div className="google-business-connected-panel">
                <strong>Google Business Profile connected</strong>
                <p>
                  {connection?.google_location_title ||
                    "Your selected business location is connected."}
                </p>

                <div className="google-business-details">
                  <div>
                    <small>Google account</small>
                    <span>{connection?.google_account_name || "Connected"}</span>
                  </div>
                  <div>
                    <small>Location</small>
                    <span>{connection?.google_location_id || "Connected"}</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="google-business-secondary-button"
                onClick={handleConnect}
                disabled={connecting}
              >
                {connecting ? "Connecting..." : "Reconnect Google"}
              </button>
            </>
          ) : connection?.google_account_name ? (
            <>
              <div className="google-business-connected-panel pending">
                <strong>Select your business location</strong>
                <p>
                  This Google account manages one or more locations. Select the
                  location that AI Reviewer should manage.
                </p>
              </div>

              <div className="google-business-locations">
                {locations.length === 0 ? (
                  <div className="google-business-empty">
                    No Business Profile locations were found for this Google account.
                  </div>
                ) : (
                  locations.map((location) => (
                    <button
                      type="button"
                      className="google-business-location"
                      key={location.name}
                      onClick={() => handleSelectLocation(location.name)}
                      disabled={selecting}
                    >
                      <span className="google-business-location-icon">G</span>
                      <span className="google-business-location-copy">
                        <strong>{location.title || "Business location"}</strong>
                        <small>{location.location_id}</small>
                      </span>
                      <span className="google-business-location-arrow">→</span>
                    </button>
                  ))
                )}
              </div>
            </>
          ) : (
            <>
              <div className="google-business-connect-copy">
                <h3>Connect your Google Business Profile</h3>
                <p>
                  You will be redirected to Google to securely authorize AI
                  Reviewer. Your Google password is never entered into AI Reviewer.
                </p>
                <ul>
                  <li>Authorization is handled directly by Google.</li>
                  <li>AI Reviewer only requests the Business Profile permission it needs.</li>
                  <li>You can revoke access from your Google account.</li>
                </ul>
              </div>

              <button
                type="button"
                className="google-business-connect-button"
                onClick={handleConnect}
                disabled={connecting}
              >
                <span className="google-business-button-mark">G</span>
                <span>{connecting ? "Opening Google..." : "Connect Google Business"}</span>
                <span>→</span>
              </button>
            </>
          )}
        </section>

        <footer className="google-business-footer">
          <span>AI Reviewer</span>
          <span>•</span>
          <span>Secure Google Business connection</span>
        </footer>
      </div>
    </main>
  );
}
