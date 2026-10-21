import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import "./dashboard.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function Dashboard() {
  const navigate = useNavigate();
  const { dashboardId } = useParams();

  const [dashboards, setDashboards] = useState([]);
  const [selectedDashboard, setSelectedDashboard] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [selectedOptions, setSelectedOptions] = useState({});
  const [business, setBusiness] = useState(null);

  const [dashboardName, setDashboardName] = useState("");
  const [questionCount, setQuestionCount] = useState(4);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  // Review history modal state.
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyDashboard, setHistoryDashboard] = useState(null);
  const [reviewHistory, setReviewHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const getToken = () => localStorage.getItem("access_token");

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("auth_user");
    navigate("/login", { replace: true });
  };

  const apiFetch = async (url, options = {}) => {
    const token = getToken();

    if (!token) {
      logout();
      throw new Error("Authentication required.");
    }

    const response = await fetch(url, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.status === 401) {
      logout();
      throw new Error("Your session has expired.");
    }

    return response;
  };

  const loadDashboards = async () => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/dashboard`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to load dashboards."
      );
    }

    setDashboards(data.dashboards || []);
    setBusiness(data.business || null);
  };

  const loadDashboard = async (id) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/dashboard/${id}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to load dashboard."
      );
    }

    setSelectedDashboard(data.dashboard);
    setBusiness((current) => ({
      ...current,
      business_name:
        data.dashboard.business_name ||
        current?.business_name,
      year_established:
        data.dashboard.year_established ||
        current?.year_established,
    }));
  };

  const loadQuestions = async (id) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/query/questions?dashboard_id=${id}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to load questions."
      );
    }

    setQuestions(data.questions || []);
  };

  useEffect(() => {
    if (!historyOpen) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        closeReviewHistory();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [historyOpen, historyLoading]);

  useEffect(() => {
    const initialize = async () => {
      setLoading(true);
      setError("");

      try {
        await loadDashboards();

        if (dashboardId) {
          await loadDashboard(dashboardId);
          await loadQuestions(dashboardId);
        }
      } catch (err) {
        console.error("Dashboard initialization failed:", err);
        setError(
          err.message || "Unable to load dashboard."
        );
      } finally {
        setLoading(false);
      }
    };

    initialize();
  }, [dashboardId]);

  const createDashboard = async (event) => {
    event.preventDefault();

    const name = dashboardName.trim();

    if (name.length < 2) {
      setError("Enter a dashboard name.");
      return;
    }

    setWorking(true);
    setError("");

    let createdDashboardId = null;
    let generationSucceeded = false;

    const deleteCreatedDashboard = async () => {
      if (!createdDashboardId) return;

      try {
        const cleanupResponse = await apiFetch(
          `${API_BASE_URL}/api/dashboard/${createdDashboardId}`,
          { method: "DELETE" }
        );

        if (!cleanupResponse.ok) {
          console.error(
            "Automatic dashboard cleanup failed.",
            await cleanupResponse.text()
          );
        }
      } catch (cleanupError) {
        console.error(
          "Automatic dashboard cleanup failed:",
          cleanupError
        );
      }
    };

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/dashboard`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            dashboard_name: name,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to create dashboard."
        );
      }

      const dashboard = data.dashboard;
      const dashboardId = dashboard?.dashboard_id;
      createdDashboardId = dashboardId;

      if (!dashboardId) {
        throw new Error(
          "Dashboard was created, but its ID could not be determined."
        );
      }

      // Generate exactly the number of questions selected for THIS dashboard.
      const generateResponse = await apiFetch(
        `${API_BASE_URL}/api/query/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            dashboard_id: dashboardId,
            question_count: Number(questionCount),
          }),
        }
      );

      const generateData = await generateResponse.json();

      if (!generateResponse.ok) {
        throw new Error(
          generateData.detail ||
            "Dashboard was created, but questions could not be generated."
        );
      }

      if (
        !Array.isArray(generateData.questions) ||
        generateData.questions.length !== Number(questionCount)
      ) {
        throw new Error(
          `AI generated ${
            generateData.questions?.length || 0
          } questions instead of ${questionCount}.`
        );
      }

      generationSucceeded = true;

      setDashboardName("");
      await loadDashboards();

      // Open Query Maker with the questions already generated here.
      // Query Maker should display these questions instead of generating again.
      navigate(`/query-maker/${dashboardId}`, {
        replace: true,
        state: {
          generatedQuestions: generateData.questions,
          questionCount: Number(questionCount),
          dashboardId,
          dashboard,
        },
      });
    } catch (err) {
      if (createdDashboardId && !generationSucceeded) {
        await deleteCreatedDashboard();
      }

      setError(
        err.message || "Unable to create dashboard."
      );
    } finally {
      setWorking(false);
    }
  };

  const openReviewHistory = async (dashboard) => {
    setHistoryDashboard(dashboard);
    setHistoryOpen(true);
    setHistoryLoading(true);
    setHistoryError("");
    setReviewHistory([]);

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/dashboard/${dashboard.dashboard_id}/history`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to load review history."
        );
      }

      setReviewHistory(data.reviews || []);
    } catch (err) {
      console.error("Review history loading failed:", err);
      setHistoryError(
        err.message || "Unable to load review history."
      );
    } finally {
      setHistoryLoading(false);
    }
  };

  const closeReviewHistory = () => {
    if (historyLoading) return;

    setHistoryOpen(false);
    setHistoryDashboard(null);
    setReviewHistory([]);
    setHistoryError("");
  };

  const deleteDashboard = async (id) => {
    const target = dashboards.find(
      (item) => item.dashboard_id === id
    );

    if (!target) return;

    const confirmed = window.confirm(
      `Delete "${target.dashboard_name}"? Its questions and options will also be deleted.`
    );

    if (!confirmed) return;

    setWorking(true);
    setError("");

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/dashboard/${id}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to delete dashboard."
        );
      }

      if (dashboardId === String(id)) {
        navigate("/dashboard", { replace: true });
      }

      await loadDashboards();
    } catch (err) {
      setError(
        err.message || "Unable to delete dashboard."
      );
    } finally {
      setWorking(false);
    }
  };

  const toggleOption = (queryId, optionText) => {
    setSelectedOptions((current) => {
      const existing = current[queryId] || [];
      const selected = existing.includes(optionText);

      return {
        ...current,
        [queryId]: selected
          ? existing.filter((item) => item !== optionText)
          : [...existing, optionText],
      };
    });

    setError("");
  };

  const generateReview = async () => {
    if (!questions.length) {
      setError(
        "This dashboard does not have a questionnaire yet."
      );
      return;
    }

    const answers = questions.map((question) => ({
      query_id: question.query_id,
      question: question.question,
      selected_options: selectedOptions[question.query_id] || [],
    }));

    const incomplete = answers.find(
      (answer) => answer.selected_options.length === 0
    );

    if (incomplete) {
      setError(
        "Please select at least one option for every question."
      );
      return;
    }

    setWorking(true);
    setError("");

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/reviews/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            answers,
            dashboard_id: selectedDashboard?.dashboard_id || null,
            regenerate_status: 0,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to generate the review."
        );
      }

      navigate("/review", {
        state: {
          review: data.review,
          reviewId: data.review_id,
          answers,
          dashboard: selectedDashboard,
        },
      });
    } catch (err) {
      console.error("Review generation failed:", err);
      setError(
        err.message || "Unable to generate the review."
      );
    } finally {
      setWorking(false);
    }
  };

  if (loading) {
    return (
      <main className="dashboard-page">
        <div className="dashboard-loading">
          <div className="dashboard-spinner" />
          <p>Loading dashboard...</p>
        </div>
      </main>
    );
  }

  if (!dashboardId) {
    return (
      <main className="dashboard-page">
        <div className="dashboard-container">
          <header className="dashboard-manager-header">
            <span className="dashboard-kicker">
              WORKSPACES
            </span>

            <h1>Your Dashboards</h1>

            <p>
              Create separate customer experience
              questionnaires for different use cases.
            </p>

            {business?.business_name && (
              <div className="dashboard-business-pill">
                <strong>{business.business_name}</strong>
                {business.year_established && (
                  <span>
                    Established {business.year_established}
                  </span>
                )}
              </div>
            )}
          </header>

          {error && (
            <div className="dashboard-message error">
              {error}
            </div>
          )}

          <form
            className="dashboard-create-card"
            onSubmit={createDashboard}
          >
            <div>
              <span className="dashboard-card-label">
                NEW DASHBOARD
              </span>
              <h2>Create a dashboard</h2>
              <p>
                Give this customer experience workflow a
                clear name.
              </p>
            </div>

            <input
              value={dashboardName}
              onChange={(event) =>
                setDashboardName(event.target.value)
              }
              placeholder="e.g. Default Feedback"
              maxLength={150}
              disabled={working}
            />

            <div className="dashboard-question-count">
              <div className="dashboard-question-count-header">
                <div>
                  <strong>Number of questions</strong>
                  <span>Choose 2 to 8 questions for this dashboard.</span>
                </div>

                <div className="dashboard-question-count-value">
                  {questionCount}
                </div>
              </div>

              <input
                id="dashboard-question-count"
                type="range"
                min="2"
                max="8"
                step="1"
                value={questionCount}
                onChange={(event) =>
                  setQuestionCount(Number(event.target.value))
                }
                className="dashboard-question-slider"
                disabled={working}
                aria-label="Number of questions"
              />

              <div className="dashboard-question-scale" aria-hidden="true">
                {[2, 3, 4, 5, 6, 7, 8].map((number) => (
                  <span key={number}>{number}</span>
                ))}
              </div>

              <p>
                AI will generate {questionCount} customer questions with relevant options for each question.
              </p>
            </div>

            <button type="submit" disabled={working}>
              {working ? "Creating..." : "Create Dashboard"}
              <span>+</span>
            </button>
          </form>

          <section className="dashboard-list-section">
            <div className="dashboard-section-heading">
              <div>
                <span className="dashboard-kicker">
                  YOUR WORKSPACES
                </span>
                <h2>
                  {dashboards.length}{" "}
                  {dashboards.length === 1
                    ? "dashboard"
                    : "dashboards"}
                </h2>
              </div>
            </div>

            {dashboards.length === 0 ? (
              <div className="dashboard-empty">
                <div className="dashboard-empty-icon">
                  +
                </div>
                <h3>No dashboards yet</h3>
                <p>
                  Create your first dashboard above.
                </p>
              </div>
            ) : (
              <div className="dashboard-grid">
                {dashboards.map((item) => (
                  <article
                    className="dashboard-card"
                    key={item.dashboard_id}
                  >
                    <div className="dashboard-card-top">
                      <button
                        type="button"
                        className="dashboard-card-main"
                        onClick={() =>
                          navigate(
                            `/customer-dashboard/${item.public_url_id}`
                          )
                        }
                      >
                        <div className="dashboard-card-icon">
                          Q
                        </div>

                        <div className="dashboard-card-copy">
                          <span>
                            {item.question_count || 0} questions
                          </span>
                          <h3>{item.dashboard_name}</h3>
                          {item.updated_at_formatted && (
                            <p className="dashboard-card-last-updated">
                              Last updated · {item.updated_at_formatted}
                            </p>
                          )}
                        </div>

                        <span className="dashboard-card-arrow" aria-hidden="true">
                          →
                        </span>
                      </button>

                      <button
                        type="button"
                        className="dashboard-history-button"
                        onClick={() => openReviewHistory(item)}
                        disabled={working}
                        aria-label={`View review history for ${item.dashboard_name}`}
                        title="Review history"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                          focusable="false"
                        >
                          <path
                            d="M3 12a9 9 0 1 0 3-6.7"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.9"
                            strokeLinecap="round"
                          />
                          <path
                            d="M3 5.5v5h5"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.9"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          <path
                            d="M12 7v5l3.2 2"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.9"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                        <span className="dashboard-history-button-label">
                          History
                        </span>
                      </button>
                    </div>

                    <div className="dashboard-card-actions">
                      <button
                        type="button"
                        className="dashboard-manage"
                        onClick={() =>
                          navigate(`/query-maker/${item.dashboard_id}`)
                        }
                        disabled={working}
                      >
                        <span className="dashboard-manage-icon">✎</span>
                        <span>Manage Questions</span>
                      </button>

                      <button
                        type="button"
                        className="dashboard-delete"
                        onClick={() =>
                          deleteDashboard(item.dashboard_id)
                        }
                        disabled={working}
                      >
                        Delete
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

        {historyOpen && (
          <div
            className="dashboard-history-overlay"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                closeReviewHistory();
              }
            }}
          >
            <section
              className="dashboard-history-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="dashboard-history-title"
            >
              <header className="dashboard-history-header">
                <div className="dashboard-history-heading">
                  <span className="dashboard-history-kicker">
                    REVIEW HISTORY
                  </span>
                  <h2 id="dashboard-history-title">
                    {historyDashboard?.dashboard_name || "Review history"}
                  </h2>
                  <p>
                    Every review generated from this dashboard.
                  </p>
                </div>

                <button
                  type="button"
                  className="dashboard-history-close"
                  onClick={closeReviewHistory}
                  disabled={historyLoading}
                  aria-label="Close review history"
                >
                  <span aria-hidden="true">×</span>
                </button>
              </header>

              <div className="dashboard-history-body">
                {historyLoading ? (
                  <div className="dashboard-history-loading">
                    <div className="dashboard-history-spinner" />
                    <strong>Loading review history...</strong>
                    <span>Please wait a moment.</span>
                  </div>
                ) : historyError ? (
                  <div className="dashboard-history-state dashboard-history-error">
                    <div className="dashboard-history-state-icon">!</div>
                    <h3>Unable to load history</h3>
                    <p>{historyError}</p>
                    <button
                      type="button"
                      onClick={() => {
                        if (historyDashboard) {
                          openReviewHistory(historyDashboard);
                        }
                      }}
                    >
                      Try again
                    </button>
                  </div>
                ) : reviewHistory.length === 0 ? (
                  <div className="dashboard-history-state">
                    <div className="dashboard-history-state-icon">◷</div>
                    <h3>No reviews yet</h3>
                    <p>
                      Reviews generated from this dashboard will appear here
                      automatically.
                    </p>
                  </div>
                ) : (
                  <div className="dashboard-history-list">
                    {reviewHistory.map((review, index) => (
                      <article
                        className="dashboard-history-item"
                        key={review.review_id}
                      >
                        <div className="dashboard-history-item-top">
                          <div className="dashboard-history-item-number">
                            #{reviewHistory.length - index}
                          </div>

                          <div className="dashboard-history-item-meta">
                            <span>
                              {review.created_time_formatted || "Date unavailable"}
                            </span>

                            <div className="dashboard-history-badges">
                              {review.regenerate_status === 1 && (
                                <span className="dashboard-history-badge regenerated">
                                  Regenerated
                                </span>
                              )}

                              {review.submit_status === 1 ? (
                                <span className="dashboard-history-badge submitted">
                                  Submitted
                                </span>
                              ) : review.submit_status === 0 ? (
                                <span className="dashboard-history-badge not-submitted">
                                  Not submitted
                                </span>
                              ) : (
                                <span className="dashboard-history-badge pending">
                                  Not attempted
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <p className="dashboard-history-review-text">
                          {review.review_text}
                        </p>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              {!historyLoading && !historyError && reviewHistory.length > 0 && (
                <footer className="dashboard-history-footer">
                  <span>
                    {reviewHistory.length}{" "}
                    {reviewHistory.length === 1 ? "review" : "reviews"}
                  </span>
                  <span>Newest first</span>
                </footer>
              )}
            </section>
          </div>
        )}
      </main>
    );
  }


}

export default Dashboard;
