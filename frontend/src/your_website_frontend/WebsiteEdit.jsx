import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import "./website_edit.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const DEFAULT_REQUEST_TIMEOUT_MS = 30000;

// Website regeneration includes Gemini + Unsplash work and can legitimately
// take longer than a normal API request. Keep this comfortably above the
// expected generation time so a successful backend update is not reported
// as a client-side failure.
const WEBSITE_UPDATE_TIMEOUT_MS = 180000;

function getAuthToken() {
  return localStorage.getItem("access_token");
}

function handleUnauthorized(navigate) {
  localStorage.removeItem("access_token");
  localStorage.removeItem("auth_user");
  navigate("/login", { replace: true });
}

async function requestJson(
  url,
  options = {},
  fallbackMessage = "Request failed.",
  timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS
) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    timeoutMs
  );

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
        "Website generation is taking longer than expected. Please check Website History before trying again, because the update may have already completed."
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function EditWebsite() {
  const navigate = useNavigate();
  const { websiteVersionId } = useParams();

  const versionId = useMemo(
    () => Number(websiteVersionId),
    [websiteVersionId]
  );

  const [business, setBusiness] = useState(null);
  const [websiteVersion, setWebsiteVersion] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [colorTheme1, setColorTheme1] = useState(null);
  const [colorTheme2, setColorTheme2] = useState(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadVersion = useCallback(async () => {
    if (!Number.isInteger(versionId) || versionId <= 0) {
      setError("Invalid website version.");
      setLoading(false);
      return;
    }

    const token = getAuthToken();

    if (!token) {
      handleUnauthorized(navigate);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const data = await requestJson(
        `${API_BASE_URL}/api/your-website/edit/${versionId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
        "Unable to load this website for editing."
      );

      setBusiness(data.business || null);
      setWebsiteVersion(data.website_version || null);
      setQuestions(
        Array.isArray(data.questions)
          ? data.questions
          : []
      );
      setColorTheme1(data.website_version?.color_theme_1 || null);
      setColorTheme2(data.website_version?.color_theme_2 || null);
      setAnswers(
        data.answers && typeof data.answers === "object"
          ? data.answers
          : {}
      );
    } catch (error) {
      console.error("Website edit loading failed:", error);

      if (error?.status === 401) {
        handleUnauthorized(navigate);
        return;
      }

      setError(
        error.message ||
          "Unable to load this website for editing."
      );
    } finally {
      setLoading(false);
    }
  }, [navigate, versionId]);

  useEffect(() => {
    loadVersion();
  }, [loadVersion]);

  const handleColorChange = (setter, value) => {
    setter(value ? value.toUpperCase() : null);
    setError("");
  };

  const updateAnswer = (questionId, value) => {
    setAnswers((previous) => ({
      ...previous,
      [String(questionId)]: value,
    }));
  };

  const hasMissingRequired = questions.some(
    (question) =>
      question.required &&
      !String(
        answers[String(question.question_id)] || ""
      ).trim()
  );

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (saving || hasMissingRequired) {
      return;
    }

    const token = getAuthToken();

    if (!token) {
      handleUnauthorized(navigate);
      return;
    }

    const payload = {
      color_theme_1: colorTheme1,
      color_theme_2: colorTheme2,
      answers: questions.map((question) => ({
        question_id: Number(question.question_id),
        answer: String(
          answers[String(question.question_id)] || ""
        ).trim(),
      })),
    };

    try {
      setSaving(true);
      setError("");

      const data = await requestJson(
        `${API_BASE_URL}/api/your-website/edit/${versionId}/generate`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
        "Unable to update your website.",
        WEBSITE_UPDATE_TIMEOUT_MS
      );

      if (data.public_url_id) {
        navigate(
          `/your-website/preview/${encodeURIComponent(
            data.public_url_id
          )}`,
          { replace: true }
        );
        return;
      }

      navigate("/your-website/history", {
        replace: true,
      });
    } catch (error) {
      console.error("Website update failed:", error);

      if (error?.status === 401) {
        handleUnauthorized(navigate);
        return;
      }

      setError(
        error.message ||
          "Unable to update this website version. The existing version is still unchanged."
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <main className="website-edit-page">
        <section className="website-edit-loading">
          <div className="website-edit-spinner" />
          <strong>Loading website editor</strong>
          <span>Preparing your saved questions and answers...</span>
        </section>
      </main>
    );
  }

  if (error && !questions.length) {
    return (
      <main className="website-edit-page">
        <section className="website-edit-error">
          <span className="website-edit-kicker">WEBSITE EDITOR</span>
          <h1>Unable to open this website</h1>
          <p>{error}</p>
          <button
            type="button"
            onClick={() => navigate("/your-website/history")}
          >
            Back to Website History
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="website-edit-page">
      <div className="website-edit-shell">
        <header className="website-edit-header">
<div>
            <span className="website-edit-kicker">EDIT WEBSITE</span>
            <h1>{business?.business_name || "Your Website"}</h1>
            <p>
              Editing saved version{" "}
              <strong>V{websiteVersion?.version_number || "—"}</strong>.
              Saving updates this exact version.
            </p>
          </div>

          <span className="website-edit-version">
            V{websiteVersion?.version_number || "—"}
          </span>
        </header>

        {error && (
          <div className="website-edit-alert" role="alert">
            <strong>Update could not be completed</strong>
            <span>{error}</span>
          </div>
        )}

        <section className="website-edit-intro">
          <div>
            <span>EDITABLE CONTENT</span>
            <strong>Update the information behind this website</strong>
          </div>
          <p>
            Change any answer below. Saving regenerates the website and
            updates this exact history version in place.
          </p>
        </section>

        <form className="website-edit-form" onSubmit={handleSubmit}>
          <section className="website-edit-color-theme" aria-labelledby="website-edit-color-title">
            <div>
              <span className="website-edit-kicker">OPTIONAL BRANDING</span>
              <h2 id="website-edit-color-title">Website color theme</h2>
              <p>Choose two colors or leave either one on AI choose. Saving updates this exact version.</p>
            </div>

            <div className="website-edit-color-grid">
              {[
                { label: "Primary color", value: colorTheme1, setter: setColorTheme1 },
                { label: "Secondary color", value: colorTheme2, setter: setColorTheme2 },
              ].map((item) => (
                <div className="website-edit-color-card" key={item.label}>
                  <div className="website-edit-color-card-top">
                    <label>{item.label}</label>
                    <span>{item.value || "AI choose"}</span>
                  </div>
                  <div className="website-edit-color-control">
                    <div
                      className={`website-edit-color-picker ${!item.value ? "empty" : ""}`}
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
                      className={`website-edit-ai-color-button ${!item.value ? "active" : ""}`}
                      onClick={() => handleColorChange(item.setter, null)}
                      disabled={saving}
                    >
                      {item.value ? "Let AI choose" : "AI will choose"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <div className="website-edit-question-list">
            {questions.map((question, index) => {
              const questionId = String(question.question_id);
              const value = answers[questionId] || "";

              return (
                <article
                  className="website-edit-question"
                  key={question.question_id}
                >
                  <div className="website-edit-question-head">
                    <span>
                      {String(index + 1).padStart(2, "0")}
                    </span>

                    <div>
                      <label htmlFor={`website-edit-${question.question_id}`}>
                        {question.question_text}
                        {question.required && (
                          <em aria-label="Required">*</em>
                        )}
                      </label>

                      {question.helper_text && (
                        <small>{question.helper_text}</small>
                      )}
                    </div>
                  </div>

                  <textarea
                    id={`website-edit-${question.question_id}`}
                    value={value}
                    onChange={(event) =>
                      updateAnswer(
                        question.question_id,
                        event.target.value
                      )
                    }
                    placeholder={
                      question.placeholder ||
                      "Enter your answer..."
                    }
                    maxLength={10000}
                    disabled={saving}
                    required={Boolean(question.required)}
                  />
                </article>
              );
            })}
          </div>

          <footer className="website-edit-footer">
            <div>
              <strong>Update this website version</strong>
              <span>
                The same version number and public URL will be kept.
              </span>
            </div>

            <div className="website-edit-footer-actions">
              <button
                type="button"
                className="website-edit-cancel"
                onClick={() => navigate("/your-website/history")}
                disabled={saving}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="website-edit-save"
                disabled={
                  saving ||
                  hasMissingRequired ||
                  !questions.length
                }
              >
                {saving
                  ? "Updating Website..."
                  : "Save & Update Website"}
              </button>
            </div>
          </footer>
        </form>
      </div>
    </main>
  );
}

export default EditWebsite;
