import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./menu.css";

function Menu() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  const handleNavigation = (path) => {
    navigate(path);
  };

  const ArrowIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M5 12h13M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );

  return (
    <div className="menu-page">
      <div className="menu-container">
        <header className="menu-header">
          <div className="menu-topbar">
            <div className="menu-brand">
              <div className="menu-brand-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path
                    d="M12 3.5 4.5 7.2v5.6c0 4.2 2.9 6.8 7.5 8.1 4.6-1.3 7.5-3.9 7.5-8.1V7.2L12 3.5Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinejoin="round"
                  />
                  <path
                    d="m8.5 12.1 2.2 2.2 4.8-5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <div>
                <h1>Business Management</h1>
                <p>Customer Experience</p>
              </div>
            </div>

            <div className="menu-status">
              <span className="menu-status-dot" />
              Active
            </div>
          </div>

          <div className="menu-welcome">
            <span className="menu-eyebrow">CONTROL CENTER</span>
            <h2>Welcome back</h2>
            <p>
              Manage your business, customer experience dashboards,
              and Google reviews from one place.
            </p>
          </div>
        </header>

        <main className="menu-content">
          <button
            className="menu-card"
            onClick={() => handleNavigation("/business-info")}
            type="button"
          >
            <div className="menu-card-top">
              <div className="menu-card-icon business-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path
                    d="M4 21h16M6.5 21V9.5h11V21M9 9.5V6.5h6v3M8.5 13h1M8.5 16.5h1M14.5 13h1M14.5 16.5h1"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <span className="menu-card-arrow"><ArrowIcon /></span>
            </div>

            <div className="menu-card-content">
              <span className="menu-card-label">SETUP</span>
              <h3>Business Info</h3>
              <p>Add and manage your business information.</p>
            </div>
          </button>

          <button
            className="menu-card"
            onClick={() => handleNavigation("/dashboard")}
            type="button"
          >
            <div className="menu-card-top">
              <div className="menu-card-icon dashboard-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <rect
                    x="4"
                    y="4"
                    width="16"
                    height="16"
                    rx="3"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path
                    d="M8 9h8M8 12h5M8 15h8"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <span className="menu-card-arrow"><ArrowIcon /></span>
            </div>

            <div className="menu-card-content">
              <span className="menu-card-label">WORKSPACES</span>
              <h3>Dashboards</h3>
              <p>
                Create and manage multiple customer experience
                dashboards.
              </p>
            </div>
          </button>


          <button
            className="menu-card"
            onClick={() => handleNavigation("/your-website")}
            type="button"
          >
            <div className="menu-card-top">
              <div className="menu-card-icon website-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <rect
                    x="3.5"
                    y="4.5"
                    width="17"
                    height="15"
                    rx="2.5"
                    stroke="currentColor"
                    strokeWidth="1.7"
                  />
                  <path
                    d="M3.5 9h17M8 13h8M8 16h5"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <span className="menu-card-arrow"><ArrowIcon /></span>
            </div>

            <div className="menu-card-content">
              <span className="menu-card-label">WEBSITE BUILDER</span>
              <h3>Your Own Product Website</h3>
              <p>
                Create a professional website for your business with AI.
              </p>
            </div>
          </button>

          <button
            className="menu-card"
            onClick={() => handleNavigation("/google-business")}
            type="button"
          >
            <div className="menu-card-top">
              <div className="menu-card-icon review-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path
                    d="M5 5.5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-4.2 3v-3H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2Z"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="m12 8 1.05 2.13 2.35.34-1.7 1.66.4 2.34L12 13.36l-2.1 1.11.4-2.34-1.7-1.66 2.35-.34L12 8Z"
                    stroke="currentColor"
                    strokeWidth="1.45"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <span className="menu-card-arrow"><ArrowIcon /></span>
            </div>

            <div className="menu-card-content">
              <span className="menu-card-label">GOOGLE REVIEWS</span>
              <h3>Review Reply</h3>
              <p>
                Connect Google Business and manage customer review
                replies.
              </p>
            </div>
          </button>
        </main>

        <footer className="menu-footer">
          <div className="menu-footer-line" />
          <p><span>AI-powered</span> review management</p>
        </footer>
      </div>
    </div>
  );
}

export default Menu;
