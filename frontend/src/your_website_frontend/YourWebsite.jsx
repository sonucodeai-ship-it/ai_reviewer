import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./your_website.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const REQUEST_TIMEOUT_MS = 180000;

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
          : Array.isArray(data.detail)
            ? data.detail.map((item) => item?.msg).filter(Boolean).join(" ")
            : fallbackMessage;

      const error = new Error(detail || fallbackMessage);
      error.status = response.status;
      throw error;
    }

    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        "Showcase generation is taking longer than expected. Please wait a little longer and try again if it does not finish."
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function YourWebsite() {
  const navigate = useNavigate();
  const mountedRef = useRef(true);

  const [business, setBusiness] = useState(null);
  const [website, setWebsite] = useState(null);
  const [websiteVersion, setWebsiteVersion] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [colorTheme1, setColorTheme1] = useState(null);
  const [colorTheme2, setColorTheme2] = useState(null);

  const [loading, setLoading] = useState(true);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [generatingWebsite, setGeneratingWebsite] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadSetup = useCallback(async () => {
    const token = getAuthToken();

    if (!token) {
      handleUnauthorized(navigate);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await requestJson(
        `${API_BASE_URL}/api/your-website`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
        "Unable to load customer showcase builder."
      );

      if (!mountedRef.current) return;

      setBusiness(data.business || null);
      setWebsite(data.website || null);
      setWebsiteVersion(data.website_version || null);
      setQuestions(Array.isArray(data.questions) ? data.questions : []);
      setColorTheme1(data.website_version?.color_theme_1 || null);
      setColorTheme2(data.website_version?.color_theme_2 || null);

      const existingAnswers = data.answers || {};
      setAnswers(
        Object.fromEntries(
          Object.entries(existingAnswers).map(([questionId, answer]) => [
            String(questionId),
            answer == null ? "" : String(answer),
          ])
        )
      );
    } catch (error) {
      console.error("Website builder loading failed:", error);

      if (error?.status === 401) {
        handleUnauthorized(navigate);
        return;
      }

      if (mountedRef.current) {
        setError(error.message || "Unable to load customer showcase builder.");
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [navigate]);

  useEffect(() => {
    loadSetup();
  }, [loadSetup]);

  const generateQuestions = useCallback(async () => {
    const token = getAuthToken();

    if (!token) {
      handleUnauthorized(navigate);
      return;
    }

    try {
      setGeneratingQuestions(true);
      setError("");
      setSuccess("");

      const data = await requestJson(
        `${API_BASE_URL}/api/your-website/questions/generate`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
        "Unable to generate showcase questions."
      );

      const generatedQuestions = Array.isArray(data.questions)
        ? data.questions
        : [];

      if (!generatedQuestions.length) {
        throw new Error("AI did not return any showcase questions.");
      }

      if (!mountedRef.current) return;

      setWebsite(data.website || null);
      setWebsiteVersion(data.website_version || null);
      setQuestions(generatedQuestions);
      setAnswers({});
      setColorTheme1(null);
      setColorTheme2(null);
      setSuccess("Your business-specific questions are ready.");
    } catch (error) {
      console.error("Website question generation failed:", error);

      if (error?.status === 401) {
        handleUnauthorized(navigate);
        return;
      }

      if (mountedRef.current) {
        setError(error.message || "Unable to generate showcase questions.");
      }
    } finally {
      if (mountedRef.current) {
        setGeneratingQuestions(false);
      }
    }
  }, [navigate]);

  const answeredCount = useMemo(
    () =>
      questions.filter((question) =>
        String(answers[question.question_id] || "").trim()
      ).length,
    [answers, questions]
  );

  const requiredCount = useMemo(
    () => questions.filter((question) => Boolean(question.required)).length,
    [questions]
  );

  const requiredAnsweredCount = useMemo(
    () =>
      questions.filter(
        (question) =>
          Boolean(question.required) &&
          String(answers[question.question_id] || "").trim()
      ).length,
    [answers, questions]
  );

  const handleColorChange = (setter, value) => {
    setter(value ? value.toUpperCase() : null);
    setError("");
    setSuccess("");
  };

  const handleAnswerChange = (questionId, value) => {
    setAnswers((previous) => ({
      ...previous,
      [String(questionId)]: value,
    }));
    setError("");
    setSuccess("");
  };

  const handleGenerateWebsite = async () => {
    const token = getAuthToken();

    if (!token) {
      handleUnauthorized(navigate);
      return;
    }

    if (!questions.length) {
      setError("Please generate the showcase questions first.");
      return;
    }

    const missingRequired = questions.filter(
      (question) =>
        Boolean(question.required) &&
        !String(answers[question.question_id] || "").trim()
    );

    if (missingRequired.length) {
      setError(
        `Please answer all required questions. ${missingRequired.length} required question${missingRequired.length === 1 ? "" : "s"} remaining.`
      );
      return;
    }

    try {
      setGeneratingWebsite(true);
      setError("");
      setSuccess("");

      const payload = {
        color_theme_1: colorTheme1,
        color_theme_2: colorTheme2,
        answers: questions.map((question) => ({
          question_id: Number(question.question_id),
          answer: String(answers[question.question_id] || "").trim(),
        })),
      };

      const data = await requestJson(
        `${API_BASE_URL}/api/your-website/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        },
        "Unable to generate your customer showcase."
      );

      const publicUrlId = String(data.public_url_id || "").trim();

      if (!publicUrlId) {
        throw new Error(
          "Showcase was generated, but the public URL was not returned by the server."
        );
      }

      navigate(
        `/your-website/preview/${encodeURIComponent(publicUrlId)}`,
        { replace: true }
      );
    } catch (error) {
      console.error("Website generation failed:", error);

      if (error?.status === 401) {
        handleUnauthorized(navigate);
        return;
      }

      if (mountedRef.current) {
        setError(error.message || "Unable to generate your customer showcase.");
      }
    } finally {
      if (mountedRef.current) {
        setGeneratingWebsite(false);
      }
    }
  };

  if (loading) {
    return (
      <main className="your-website-page">
        <div className="your-website-loading">
          <div className="your-website-spinner" />
          <strong>Loading your website builder</strong>
          <span>Checking your saved website setup...</span>
        </div>
      </main>
    );
  }

  if (!business) {
    return (
      <main className="your-website-page">
        <div className="your-website-shell">
          <section className="your-website-empty">
            <div className="your-website-empty-icon">!</div>
            <span className="your-website-kicker">BUSINESS INFORMATION</span>
            <h1>Complete your business information first</h1>
            <p>
              Your customer showcase is built from your saved business information and
              the answers you provide here.
            </p>
            <button
              type="button"
              className="your-website-primary-button"
              onClick={() => navigate("/business-info")}
            >
              Go to Business Info <span>→</span>
            </button>
          </section>
        </div>
      </main>
    );
  }

  const hasQuestions = questions.length > 0;
  const isDraft = websiteVersion && !String(websiteVersion.html_code || "").trim();

  return (
    <main className="your-website-page">
      <div className="your-website-shell">
        <header className="your-website-header">
          <div className="your-website-brand-mark">W</div>
          <div>
            <span className="your-website-kicker">AI CUSTOMER SHOWCASE</span>
            <h1>Create Your Business Showcase</h1>
            <p>
              Tell us about <strong>{business.business_name}</strong>. AI will
              use your business details and answers to create a customer-facing
              showcase for your facilities, services, menu, products, and rates.
            </p>
          </div>
        </header>

        {error && (
          <div className="your-website-alert" role="alert">
            <strong>Something went wrong</strong>
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="your-website-success" role="status">
            <strong>Ready</strong>
            <span>{success}</span>
          </div>
        )}

        <section className="your-website-business-card">
          <div className="your-website-business-heading">
            <div className="your-website-business-icon">✦</div>
            <div>
              <span className="your-website-section-label">YOUR BUSINESS</span>
              <h2>{business.business_name}</h2>
            </div>
          </div>

          <div className="your-website-business-grid">
            <div>
              <span>Business type</span>
              <strong>{business.business_type || "Not provided"}</strong>
            </div>
            <div>
              <span>Established</span>
              <strong>{business.year_established || "Not provided"}</strong>
            </div>
          </div>

          {business.about_business && (
            <p className="your-website-business-about">
              {business.about_business}
            </p>
          )}
        </section>

        <section className="your-website-wizard">
          <div className="your-website-wizard-top">
            <div>
              <span className="your-website-section-label">STEP 1 OF 1</span>
              <h2>Tell AI what makes your business special</h2>
              <p>
                These questions are specific to your business. Your answers help AI build a
                clear customer showcase of what you offer, including facilities,
                services, menu items, products, packages, and rates.
              </p>
            </div>
            <div className="your-website-step-count">
              {answeredCount}/{questions.length}
            </div>
          </div>

          <div className="your-website-progress" aria-hidden="true">
            <span
              style={{
                width: `${
                  questions.length
                    ? (answeredCount / questions.length) * 100
                    : 0
                }%`,
              }}
            />
          </div>

          <section className="your-website-color-theme" aria-labelledby="website-color-theme-title">
            <div className="your-website-color-theme-heading">
              <div>
                <span className="your-website-section-label">OPTIONAL BRANDING</span>
                <h3 id="website-color-theme-title">Choose your showcase colors</h3>
                <p>Leave either color on “AI choose” and the AI will select a compatible color for you.</p>
              </div>
            </div>

            <div className="your-website-color-grid">
              {[
                { label: "Primary color", value: colorTheme1, setter: setColorTheme1 },
                { label: "Secondary color", value: colorTheme2, setter: setColorTheme2 },
              ].map((item) => (
                <div className="your-website-color-card" key={item.label}>
                  <div className="your-website-color-card-top">
                    <label>{item.label}</label>
                    <span>{item.value || "AI choose"}</span>
                  </div>
                  <div className="your-website-color-control">
                    <div
                      className={`your-website-color-picker ${!item.value ? "empty" : ""}`}
                      style={item.value ? { "--selected-color": item.value } : undefined}
                    >
                      <span aria-hidden="true">{item.value ? "" : "AI"}</span>
                      <input
                        type="color"
                        value={item.value || "#FFFFFF"}
                        onChange={(event) => handleColorChange(item.setter, event.target.value)}
                        aria-label={`${item.label} picker`}
                      />
                    </div>
                    <button
                      type="button"
                      className={`your-website-ai-color-button ${!item.value ? "active" : ""}`}
                      onClick={() => handleColorChange(item.setter, null)}
                      disabled={generatingWebsite || generatingQuestions}
                    >
                      {item.value ? "Let AI choose" : "AI will choose"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {!hasQuestions ? (
            <div className="your-website-question-loading">
              <div className="your-website-spinner small" />
              <div>
                <strong>No showcase questions yet</strong>
                <span>
                  Use “Regenerate Questions” below to create the questions for
                  this customer showcase.
                </span>
              </div>
            </div>
          ) : (
            <div className="your-website-question-list">
              {questions.map((question, index) => (
                <article
                  className="your-website-question-card"
                  key={question.question_id || question.question_key || index}
                >
                  <div className="your-website-question-meta">
                    <span>QUESTION {String(index + 1).padStart(2, "0")}</span>
                    {question.required && <b>Required</b>}
                  </div>

                  <h3>{question.question_text}</h3>

                  {question.helper_text && (
                    <p className="your-website-helper">
                      {question.helper_text}
                    </p>
                  )}

                  <textarea
                    value={answers[question.question_id] || ""}
                    onChange={(event) =>
                      handleAnswerChange(
                        question.question_id,
                        event.target.value
                      )
                    }
                    placeholder={
                      question.placeholder ||
                      "Write the information customers should know..."
                    }
                    maxLength={10000}
                    aria-label={question.question_text}
                  />

                  <span className="your-website-input-hint">
                    {String(answers[question.question_id] || "").length}/10000
                  </span>
                </article>
              ))}
            </div>
          )}

          <div className="your-website-wizard-footer">
            <div>
              <strong>
                {requiredAnsweredCount}/{requiredCount} required answered
              </strong>
              <span>
                {isDraft
                  ? "AI will create the complete customer showcase from these answers."
                  : "Generate a new version when you want to update your customer showcase."}
              </span>
            </div>

            <button
              type="button"
              className="your-website-primary-button your-website-generate-button"
              onClick={handleGenerateWebsite}
              disabled={
                generatingWebsite ||
                generatingQuestions ||
                !hasQuestions ||
                requiredAnsweredCount !== requiredCount
              }
            >
              {generatingWebsite ? (
                <>
                  <span className="your-website-button-spinner" />
                  Creating showcase...
                </>
              ) : (
                <>
                  Generate Showcase <span>→</span>
                </>
              )}
            </button>
          </div>

          <div className="your-website-secondary-actions">
            <button
              type="button"
              className="your-website-secondary-button"
              onClick={generateQuestions}
              disabled={generatingQuestions || generatingWebsite}
            >
              {generatingQuestions
                ? "Generating questions..."
                : "Regenerate Questions"}
            </button>

            <button
              type="button"
              className="your-website-history-button"
              onClick={() => navigate("/your-website/history")}
              disabled={generatingQuestions || generatingWebsite}
            >
              All Showcase Histories
            </button>

          </div>
        </section>
      </div>
    </main>
  );
}

export default YourWebsite;
