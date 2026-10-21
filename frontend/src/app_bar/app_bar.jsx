import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import "./app_bar.css";

/*
 * AppBar
 * ------
 * Shared application shell for authenticated/internal pages.
 *
 * The component uses <Outlet /> so every route placed inside AppBar's
 * route automatically renders below the navigation bar.
 *
 * Customer-facing pages such as CustomerDashboard and WebsitePreview
 * should remain outside this shell.
 */
function AppBar() {
  const navigate = useNavigate();
  const location = useLocation();

  const [menuOpen, setMenuOpen] = useState(false);
  const [businessName, setBusinessName] = useState("");
  const [coinBalance, setCoinBalance] = useState(null);
  const [coinLoading, setCoinLoading] = useState(true);
  const [coinOpen, setCoinOpen] = useState(false);
  const [coinManagement, setCoinManagement] = useState(null);
  const [coinManagementLoading, setCoinManagementLoading] = useState(false);
  const [subscriptionPurchasing, setSubscriptionPurchasing] = useState(false);
  const [coinMessage, setCoinMessage] = useState("");
  const [coinError, setCoinError] = useState("");
  const [notificationOpen, setNotificationOpen] = useState(false);

  const menuRef = useRef(null);
  const coinRef = useRef(null);

  // Close the account menu when the user clicks outside it.
  useEffect(() => {
    const handlePointerDown = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }

      if (!event.target.closest(".app-bar-notifications")) {
        setNotificationOpen(false);
      }

      if (coinRef.current && !coinRef.current.contains(event.target)) {
        setCoinOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, []);

  // Close the account menu whenever the route changes.
  useEffect(() => {
    setMenuOpen(false);
    setNotificationOpen(false);
    setCoinOpen(false);
  }, [location.pathname]);

  // Load business identity and current coin balance.
  // The backend remains the single source of truth.
  useEffect(() => {
    const loadAppBarData = async () => {
      const token = localStorage.getItem("access_token");

      if (!token) {
        setCoinLoading(false);
        return;
      }

      const headers = {
        Authorization: `Bearer ${token}`,
      };

      try {
        const [businessResponse, coinResponse] =
          await Promise.all([
            fetch(
              `${import.meta.env.VITE_API_BASE_URL}/api/business/info`,
              {
                method: "GET",
                headers,
              }
            ),
            fetch(
              `${import.meta.env.VITE_API_BASE_URL}/api/coins/balance`,
              {
                method: "GET",
                headers,
              }
            ),
          ]);

        if (businessResponse.ok) {
          const data = await businessResponse.json();

          setBusinessName(
            String(data.business_name || "").trim()
          );
        }

        if (coinResponse.ok) {
          const data = await coinResponse.json();

          setCoinBalance(
            Number(data.coin_balance ?? 0)
          );
        }
      } catch (error) {
        console.error(
          "App bar data loading failed:",
          error
        );
      } finally {
        setCoinLoading(false);
      }
    };

    loadAppBarData();
  }, []);

  const loadCoinManagement = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    try {
      setCoinManagementLoading(true);
      setCoinError("");

      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/coins/management`,
        {
          method: "GET",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to load coin management.");
      }

      setCoinManagement(data);
      setCoinBalance(Number(data.coin_balance ?? 0));
    } catch (error) {
      console.error("Coin management loading failed:", error);
      setCoinError(error.message || "Unable to load coin management.");
    } finally {
      setCoinManagementLoading(false);
    }
  };

  const toggleCoinManagement = () => {
    setCoinMessage("");
    setCoinError("");
    setCoinOpen((current) => {
      const next = !current;
      if (next) loadCoinManagement();
      return next;
    });
  };

  const purchaseSubscription = async (ruleNo) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login", { replace: true });
      return;
    }

    const selectedRuleNo = Number(ruleNo);
    if (!Number.isInteger(selectedRuleNo) || selectedRuleNo <= 0) {
      setCoinError("Invalid membership plan.");
      return;
    }

    try {
      setSubscriptionPurchasing(true);
      setCoinError("");
      setCoinMessage("");

      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/coins/subscription/purchase`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ rule_no: selectedRuleNo }),
        }
      );

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(
          data.detail || "Unable to activate membership."
        );
        error.status = response.status;
        throw error;
      }

      setCoinBalance(Number(data.coin_balance ?? 0));
      setCoinMessage(
        `${data.rule_name || data.rule_code || "Membership"} is active.`
      );
      await loadCoinManagement();
    } catch (error) {
      console.error("Membership purchase failed:", error);
      setCoinError(error.message || "Unable to activate membership.");
    } finally {
      setSubscriptionPurchasing(false);
    }
  };

  const goTo = (path) => {
    setMenuOpen(false);
    navigate(path);
  };

  const handleLogout = () => {
    setMenuOpen(false);

    /*
     * Keep authentication cleanup compatible with the existing application.
     * If your login implementation uses a different storage key, replace
     * only this cleanup section.
     */
    localStorage.removeItem("token");
    localStorage.removeItem("access_token");
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("access_token");

    navigate("/login", { replace: true });
  };

  const isActive = (path) => {
    if (path === "/menu") {
      return location.pathname === "/menu";
    }

    return (
      location.pathname === path ||
      location.pathname.startsWith(`${path}/`)
    );
  };

  return (
    <div className="app-shell">
      <header className="app-bar">
        <div className="app-bar-inner">
          {/* Home */}
          <Link
            to="/menu"
            className={`app-bar-home ${
              isActive("/menu") ? "active" : ""
            }`}
            aria-label="Home"
            title="Home"
          >
            <svg
              className="app-bar-home-icon"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                d="M3 10.8 12 3l9 7.8v9.1a1.6 1.6 0 0 1-1.6 1.6H4.6A1.6 1.6 0 0 1 3 19.9v-9.1Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path
                d="M9.1 21.5v-6.2h5.8v6.2"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
            </svg>
          </Link>

          {/* Application identity */}
          <Link to="/menu" className="app-bar-brand" aria-label="AI Reviewer Home">
            <span className="app-bar-brand-mark" aria-hidden="true">
              AI
            </span>

            <span className="app-bar-brand-name">AI Reviewer</span>
          </Link>

          <div className="app-bar-spacer" />

          {/* Coins + membership management */}
          <div className="app-bar-coin-management" ref={coinRef}>
            <button
              type="button"
              className={`app-bar-coins ${coinOpen ? "open" : ""}`}
              onClick={toggleCoinManagement}
              aria-label="Open coin management"
              aria-expanded={coinOpen}
              title="Coins and membership"
            >
              <span className="app-bar-coin-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="8.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M12 7.2v9.6M8.8 9.1c.6-1 1.7-1.5 3.2-1.5 1.8 0 3.2.9 3.2 2.3 0 1.3-1.1 1.9-3.1 2.2-2 .3-3.1.9-3.1 2.2 0 1.4 1.4 2.3 3.2 2.3 1.5 0 2.6-.5 3.2-1.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              </span>
              <span className="app-bar-coins-value">
                {coinLoading ? "..." : Number(coinBalance ?? 0).toLocaleString("en-IN")}
              </span>
              <span className="app-bar-coins-label">Coins</span>
            </button>

            {coinOpen && (
              <div className="app-bar-coin-menu">
                <div className="app-bar-coin-menu-header">
                  <div>
                    <span>COIN MANAGEMENT</span>
                    <strong>{Number(coinBalance ?? 0).toLocaleString("en-IN")} coins</strong>
                  </div>
                  <span className="app-bar-coin-menu-balance">Balance</span>
                </div>

                {coinError && <div className="app-bar-coin-message error">{coinError}</div>}
                {coinMessage && <div className="app-bar-coin-message success">{coinMessage}</div>}

                {coinManagementLoading ? (
                  <div className="app-bar-coin-loading">Loading coin management...</div>
                ) : (
                  <>
                    <div className="app-bar-coin-section">
                      <div className="app-bar-coin-section-title">Pay as you use</div>
                      <div className="app-bar-coin-rule"><span>Review generated</span><strong>−1 coin</strong></div>
                      <div className="app-bar-coin-rule"><span>Website published</span><strong>−20 coins</strong></div>
                    </div>

                    <div className="app-bar-coin-section">
                      <div className="app-bar-coin-section-title">
                        Membership plans
                      </div>

                      <div className="app-bar-coin-plans">
                        {(coinManagement?.subscription_plans || []).map((plan) => {
                          const activePlan =
                            coinManagement?.subscription?.active &&
                            Number(coinManagement.subscription.rule_no) ===
                              Number(plan.rule_no);

                          const anotherPlanActive =
                            coinManagement?.subscription?.active && !activePlan;

                          const durationLabel =
                            Number(plan.duration_days) === 30
                              ? "30 days"
                              : Number(plan.duration_days) === 365
                                ? "1 year"
                                : `${plan.duration_days} days`;

                          return (
                            <div
                              className={`app-bar-coin-subscription ${
                                activePlan ? "active" : ""
                              }`}
                              key={plan.rule_no}
                            >
                              <div className="app-bar-coin-subscription-copy">
                                <span className="app-bar-coin-plan-label">
                                  {String(plan.name || "MEMBERSHIP").toUpperCase()}
                                </span>
                                <strong>Unlimited</strong>
                                <p>
                                  Unlimited website and review generation for{" "}
                                  {durationLabel}.
                                </p>

                                {activePlan ? (
                                  <small>
                                    Active until{" "}
                                    {new Date(
                                      coinManagement.subscription.expires_at
                                    ).toLocaleDateString("en-IN")}
                                  </small>
                                ) : (
                                  <small>
                                    Rule {plan.rule_no} ·{" "}
                                    {Number(plan.coins).toLocaleString("en-IN")}{" "}
                                    coins / {durationLabel}
                                  </small>
                                )}
                              </div>

                              <button
                                type="button"
                                className="app-bar-coin-subscribe-button"
                                onClick={() => purchaseSubscription(plan.rule_no)}
                                disabled={
                                  subscriptionPurchasing ||
                                  Boolean(coinManagement?.subscription?.active)
                                }
                              >
                                {subscriptionPurchasing
                                  ? "Activating..."
                                  : activePlan
                                    ? "Active"
                                    : anotherPlanActive
                                      ? "Unavailable"
                                      : `Use ${Number(plan.coins).toLocaleString("en-IN")}`}
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div className="app-bar-coin-section app-bar-coin-history-section">
                      <div className="app-bar-coin-section-title">Recent transactions</div>
                      {coinManagement?.transactions?.length ? (
                        coinManagement.transactions.slice(0, 5).map((item) => (
                          <div className="app-bar-coin-history-row" key={item.coin_transaction_history_id}>
                            <span>{item.description}</span>
                            <strong>−{item.coins}</strong>
                          </div>
                        ))
                      ) : (
                        <div className="app-bar-coin-empty">No coin transactions yet.</div>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Notifications */}
          <div className="app-bar-notifications">
            <button
              type="button"
              className={`app-bar-notification-button ${
                notificationOpen ? "open" : ""
              }`}
              onClick={() =>
                setNotificationOpen((current) => !current)
              }
              aria-label="Notifications"
              aria-expanded={notificationOpen}
              title="Notifications"
            >
              <svg
                className="app-bar-notification-icon"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  d="M18 9.8c0-3.3-2.1-5.7-6-5.7s-6 2.4-6 5.7c0 6.1-2.4 6.2-2.4 7.4h16.8C20.4 16 18 15.9 18 9.8Z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
                <path
                  d="M9.7 20h4.6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>

              <span className="app-bar-notification-dot" />
            </button>

            {notificationOpen && (
              <div className="app-bar-notification-menu">
                <div className="app-bar-notification-header">
                  <strong>Notifications</strong>
                  <span>Updates</span>
                </div>

                <div className="app-bar-notification-empty">
                  <span
                    className="app-bar-notification-empty-icon"
                    aria-hidden="true"
                  >
                    ✓
                  </span>
                  <strong>No new notifications</strong>
                  <span>
                    You’re all caught up.
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Account */}
          <div className="app-bar-account" ref={menuRef}>
            <button
              type="button"
              className={`app-bar-avatar-button ${
                menuOpen ? "open" : ""
              }`}
              onClick={() => setMenuOpen((current) => !current)}
              aria-label="Open account menu"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
            >
              <span className="app-bar-avatar" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <circle
                    cx="12"
                    cy="8"
                    r="3.25"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path
                    d="M5.5 20c.7-3.25 3-5 6.5-5s5.8 1.75 6.5 5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </span>

              <svg
                className="app-bar-chevron"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path
                  d="m5.5 7.5 4.5 4.5 4.5-4.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>

            {menuOpen && (
              <div className="app-bar-account-menu" role="menu">
                <div className="app-bar-menu-heading">
                  <span className="app-bar-menu-avatar" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <circle
                        cx="12"
                        cy="8"
                        r="3.25"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      />
                      <path
                        d="M5.5 20c.7-3.25 3-5 6.5-5s5.8 1.75 6.5 5"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                      />
                    </svg>
                  </span>

                  <div>
                    <strong>
                      {businessName || "Business"}
                    </strong>
                    <span>Account</span>
                  </div>
                </div>

                <div className="app-bar-menu-divider" />

                <button
                  type="button"
                  className={`app-bar-menu-item ${
                    isActive("/menu") ? "active" : ""
                  }`}
                  onClick={() => goTo("/menu")}
                  role="menuitem"
                >
                  <span className="app-bar-menu-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path
                        d="M3 10.8 12 3l9 7.8v9.1a1.6 1.6 0 0 1-1.6 1.6H4.6A1.6 1.6 0 0 1 3 19.9v-9.1Z"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M9.1 21.5v-6.2h5.8v6.2"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <span>Home</span>
                </button>

                <button
                  type="button"
                  className={`app-bar-menu-item ${
                    isActive("/your-website") ? "active" : ""
                  }`}
                  onClick={() => goTo("/your-website")}
                  role="menuitem"
                >
                  <span className="app-bar-menu-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <rect
                        x="3.5"
                        y="4"
                        width="17"
                        height="16"
                        rx="2.2"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      />
                      <path
                        d="M3.5 9h17M8 4v5M16 4v5"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      />
                    </svg>
                  </span>
                  <span>Your Website</span>
                </button>

                <button
                  type="button"
                  className={`app-bar-menu-item ${
                    isActive("/dashboard") ? "active" : ""
                  }`}
                  onClick={() => goTo("/dashboard")}
                  role="menuitem"
                >
                  <span className="app-bar-menu-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <rect
                        x="3.5"
                        y="3.5"
                        width="7"
                        height="7"
                        rx="1.2"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      />
                      <rect
                        x="13.5"
                        y="3.5"
                        width="7"
                        height="7"
                        rx="1.2"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      />
                      <rect
                        x="3.5"
                        y="13.5"
                        width="7"
                        height="7"
                        rx="1.2"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      />
                      <rect
                        x="13.5"
                        y="13.5"
                        width="7"
                        height="7"
                        rx="1.2"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      />
                    </svg>
                  </span>
                  <span>Dashboard</span>
                </button>

                <button
                  type="button"
                  className={`app-bar-menu-item ${
                    isActive("/qr-codes") ? "active" : ""
                  }`}
                  onClick={() => goTo("/qr-codes")}
                  role="menuitem"
                >
                  <span className="app-bar-menu-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path d="M3 3h7v7H3zM5.5 5.5v2h2v-2zM14 3h7v7h-7zM16.5 5.5v2h2v-2zM3 14h7v7H3zM5.5 16.5v2h2v-2zM13 13h3v3h-3zM18 13h3v3h-3zM13 18h3v3h-3zM18 18h3v3h-3z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                    </svg>
                  </span>
                  <span>Your QR&apos;s</span>
                </button>

                <div className="app-bar-menu-divider" />

                <button
                  type="button"
                  className="app-bar-menu-item logout"
                  onClick={handleLogout}
                  role="menuitem"
                >
                  <span className="app-bar-menu-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path
                        d="M10 4H5.5A1.5 1.5 0 0 0 4 5.5v13A1.5 1.5 0 0 0 5.5 20H10"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                      />
                      <path
                        d="M13 8l4 4-4 4M17 12H9"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <span>Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="app-shell-content">
        <Outlet />
      </main>
    </div>
  );
}

export default AppBar;
