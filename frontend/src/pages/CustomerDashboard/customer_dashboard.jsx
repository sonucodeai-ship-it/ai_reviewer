import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { businessSlugify, customerDashboardPath } from "../../qr/publicUrl";
import "./customer_dashboard.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function CustomerDashboard() {
  const navigate = useNavigate();
  const { publicUrlId, businessSlug } = useParams();

  const [selectedDashboard, setSelectedDashboard] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [selectedOptions, setSelectedOptions] = useState({});
  const [business, setBusiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const loadDashboard = async (id) => {
    const response = await fetch(
      `${API_BASE_URL}/api/dashboard/public/${id}`
    );

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to load dashboard.");
    setSelectedDashboard(data.dashboard);
    const currentBusinessName = data.dashboard.business_name || "Your Business";
    setBusiness((current) => ({
      ...current,
      business_name: currentBusinessName,
      year_established: data.dashboard.year_established || current?.year_established,
    }));

    // Canonicalize the URL using the latest business name from the API.
    // This also supports older customer-dashboard links without a slug.
    const canonicalPath = customerDashboardPath(currentBusinessName, id);
    if (businessSlug !== businessSlugify(currentBusinessName) || window.location.pathname !== canonicalPath) {
      navigate(canonicalPath, { replace: true });
    }
  };

  const loadQuestions = async (id) => {
    const response = await fetch(
      `${API_BASE_URL}/api/dashboard/public/${id}/questions`
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to load questions.");
    setQuestions(data.questions || []);
  };

  useEffect(() => {
    const initialize = async () => {
      if (!publicUrlId) { setError("Invalid dashboard link."); setLoading(false); return; }
      setLoading(true); setError("");
      try { await loadDashboard(publicUrlId); await loadQuestions(publicUrlId); }
      catch (err) { console.error("Customer dashboard initialization failed:", err); setError(err.message || "Unable to load this dashboard."); }
      finally { setLoading(false); }
    };
    initialize();
  }, [publicUrlId]);

  const toggleOption = (queryId, optionText) => {
    setSelectedOptions((current) => {
      const existing = current[queryId] || [];
      return { ...current, [queryId]: existing.includes(optionText) ? existing.filter((item) => item !== optionText) : [...existing, optionText] };
    });
    setError("");
  };

  const isComplete = questions.length > 0 && questions.every((question) => (selectedOptions[question.query_id] || []).length > 0);
  const selectedOptionCount = Object.values(selectedOptions).reduce((total, selected) => total + selected.length, 0);

  const generateReview = async () => {
    if (!questions.length) { setError("This dashboard does not have a questionnaire yet."); return; }
    const answers = questions.map((question) => ({ query_id: question.query_id, question: question.question, selected_options: selectedOptions[question.query_id] || [] }));
    if (answers.some((answer) => answer.selected_options.length === 0)) { setError("Please select at least one option for every question."); return; }
    setWorking(true); setError("");
    try {
      // Customer review generation is intentionally public.
      // Do not send or require the business owner's authentication token.
      const response = await fetch(
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
      if (!response.ok) throw new Error(data.detail || "Unable to generate the review.");
      navigate("/review", { state: { review: data.review, reviewId: data.review_id, answers, dashboard: selectedDashboard } });
    } catch (err) { console.error("Review generation failed:", err); setError(err.message || "Unable to generate the review."); }
    finally { setWorking(false); }
  };

  return (
    <main className="dashboard-customer-page">
      <div className="dashboard-customer-background-circle dashboard-customer-circle-one" />
      <div className="dashboard-customer-background-circle dashboard-customer-circle-two" />

      <div className="dashboard-customer-container dashboard-customer-detail">
        <header className="dashboard-customer-business-header">
          <div className="dashboard-customer-business-heading">
            <div className="dashboard-customer-business-logo">
              {(selectedDashboard?.business_name || business?.business_name || "B")
                .charAt(0)
                .toUpperCase()}
            </div>

            <div className="dashboard-customer-business-title">
              <h1>
                {selectedDashboard?.business_name ||
                  business?.business_name ||
                  "Your Business"}
              </h1>
              {(selectedDashboard?.year_established || business?.year_established) && (
                <span>
                  Established {selectedDashboard?.year_established || business?.year_established}
                </span>
              )}
            </div>
          </div>

          {(selectedDashboard?.year_established || business?.year_established) && (
            <div className="dashboard-customer-established-badge">
              <span className="dashboard-customer-established-icon">✓</span>
              <div>
                <small>Serving since</small>
                <strong>
                  {selectedDashboard?.year_established || business?.year_established}
                </strong>
              </div>
            </div>
          )}
        </header>

        <section className="dashboard-customer-intro">
          <span className="dashboard-customer-eyebrow">
            {selectedDashboard?.dashboard_name || "YOUR EXPERIENCE"}
          </span>

          <h2>
            Tell us about your
            <span> experience</span>
          </h2>

          <p>
            Share a few details about your experience. Your answers will help
            create a natural and personalized review.
          </p>
        </section>

        {error && (
          <div className="dashboard-message error dashboard-customer-error">
            {error}
          </div>
        )}

        {questions.length === 0 ? (
          <section className="dashboard-empty dashboard-customer-empty">
            <div className="dashboard-empty-icon">?</div>
            <h3>No questions available</h3>
            <p>
              Create your customer questions before generating a review.
            </p>
            <button
              type="button"
              onClick={() => navigate(`/query-maker/${dashboardId}`)}
            >
              Open Query Maker
              <span>→</span>
            </button>
          </section>
        ) : (
          <section className="dashboard-customer-questions-card">
            {questions.map((question, questionIndex) => {
              const questionKey = question.query_id;
              const selected = selectedOptions[questionKey] || [];

              return (
                <div
                  className="dashboard-customer-question-section"
                  key={questionKey}
                >
                  <div className="dashboard-customer-question-heading">
                    <div className="dashboard-customer-question-number">
                      {String(questionIndex + 1).padStart(2, "0")}
                    </div>

                    <div>
                      <h3>{question.question}</h3>
                      <p>Select all that apply.</p>
                    </div>
                  </div>

                  <div className="dashboard-customer-options-grid">
                    {question.options.map((option, optionIndex) => {
                      const isSelected = selected.includes(option.text);

                      return (
                        <button
                          key={
                            option.option_id ??
                            `${questionKey}-${optionIndex}`
                          }
                          type="button"
                          className={`dashboard-customer-option-card ${
                            isSelected ? "selected" : ""
                          }`}
                          onClick={() =>
                            toggleOption(question.query_id, option.text)
                          }
                          disabled={working}
                        >
                          <span className="dashboard-customer-option-icon">
                            {isSelected ? "✓" : "+"}
                          </span>
                          <span className="dashboard-customer-option-text">
                            {option.text}
                          </span>
                          <span className="dashboard-customer-selection-check">✓</span>
                        </button>
                      );
                    })}
                  </div>

                  {questionIndex < questions.length - 1 && (
                    <div className="dashboard-customer-divider" />
                  )}
                </div>
              );
            })}

            <div className="dashboard-customer-action">
              <div className="dashboard-customer-selection-status">
                <div className="dashboard-customer-status-icon">
                  {questions.every(
                    (question) =>
                      (selectedOptions[question.query_id] || []).length > 0
                  )
                    ? "✓"
                    : "!"}
                </div>

                <div>
                  <strong>
                    {questions.every(
                      (question) =>
                        (selectedOptions[question.query_id] || []).length > 0
                    )
                      ? "Ready to continue"
                      : "Almost there"}
                  </strong>
                  <span>
                    {questions.every(
                      (question) =>
                        (selectedOptions[question.query_id] || []).length > 0
                    )
                      ? `${Object.values(selectedOptions).reduce(
                          (total, selected) => total + selected.length,
                          0
                        )} ${
                          Object.values(selectedOptions).reduce(
                            (total, selected) => total + selected.length,
                            0
                          ) === 1
                            ? "selection"
                            : "selections"
                        } selected.`
                      : "Answer every question to continue."}
                  </span>
                </div>
              </div>

              <button
                type="button"
                className="dashboard-customer-continue-button"
                disabled={working}
                onClick={generateReview}
              >
                <span>{working ? "Creating review..." : "Continue"}</span>
                <span className="dashboard-customer-arrow">
                  {working ? "..." : "→"}
                </span>
              </button>
            </div>
          </section>
        )}

        <footer className="dashboard-customer-footer">
          <span>
            {selectedDashboard?.dashboard_name ||
              business?.business_name ||
              "Customer Experience"}
          </span>
          <span className="dashboard-customer-footer-dot">•</span>
          <span>Your feedback matters</span>
        </footer>
      </div>
    </main>
  );
}

export default CustomerDashboard;
