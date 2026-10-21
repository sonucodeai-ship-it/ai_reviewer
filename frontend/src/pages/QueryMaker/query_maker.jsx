import { useEffect, useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import "./query_maker.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const MIN_QUESTIONS = 2;
const MAX_QUESTIONS = 8;
const DEFAULT_QUESTIONS = 4;
const MIN_OPTIONS = 2;
const MAX_OPTIONS = 8;

function QueryMaker() {
  const navigate = useNavigate();
  const location = useLocation();
  const { dashboardId } = useParams();

  /*
   * ---------------------------------------------------------
   * ROUTE STATE
   * ---------------------------------------------------------
   *
   * Business Info / Dashboard can send:
   *
   * {
   *   generatedQuestions: [...],
   *   questionCount: 6,
   *   dashboardId: 123,
   *   dashboard: {...}
   * }
   *
   * Query Maker MUST use those questions directly.
   *
   * This prevents the previous bug where Query Maker
   * regenerated the questionnaire with its own default of 4.
   */
  const routeState = location.state || {};

  const incomingQuestions = Array.isArray(
    routeState.generatedQuestions
  )
    ? routeState.generatedQuestions
    : null;

  const incomingQuestionCount = Number(
    routeState.questionCount
  );

  const initialQuestionCount =
    incomingQuestionCount >= MIN_QUESTIONS &&
    incomingQuestionCount <= MAX_QUESTIONS
      ? incomingQuestionCount
      : DEFAULT_QUESTIONS;

  /*
   * ---------------------------------------------------------
   * STATE
   * ---------------------------------------------------------
   */

  const [dashboard, setDashboard] = useState(
    routeState.dashboard || null
  );

  const [questions, setQuestions] = useState([]);

  const [questionCount, setQuestionCount] = useState(
    incomingQuestions?.length >= MIN_QUESTIONS &&
      incomingQuestions?.length <= MAX_QUESTIONS
      ? incomingQuestions.length
      : initialQuestionCount
  );

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  /*
   * ---------------------------------------------------------
   * AUTH
   * ---------------------------------------------------------
   */

  const getToken = () => {
    return localStorage.getItem("access_token");
  };

  const handleUnauthorized = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("auth_user");

    navigate("/login", {
      replace: true,
    });
  };

  /*
   * ---------------------------------------------------------
   * API HELPER
   * ---------------------------------------------------------
   */

  const apiFetch = async (url, options = {}) => {
    const token = getToken();

    if (!token) {
      handleUnauthorized();
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
      let errorMessage = "Authentication failed.";

      try {
        const errorData = await response.clone().json();

        if (errorData?.detail) {
          errorMessage = errorData.detail;
        }
      } catch {
        // Ignore invalid JSON responses.
      }

      console.error(
        "API authentication error:",
        errorMessage
      );

      handleUnauthorized();

      throw new Error(errorMessage);
    }

    return response;
  };

  /*
   * ---------------------------------------------------------
   * NORMALIZE QUESTIONS
   * ---------------------------------------------------------
   *
   * Makes AI-generated questions and database questions
   * follow exactly the same frontend structure.
   */

  const normalizeQuestions = (items) => {
    if (!Array.isArray(items)) {
      return [];
    }

    return items.map((item, questionIndex) => ({
      localId:
        item.localId ||
        `question-${Date.now()}-${questionIndex}`,

      query_id: item.query_id ?? null,

      dashboard_id: Number(dashboardId),

      question:
        typeof item.question === "string"
          ? item.question
          : "",

      options: Array.isArray(item.options)
        ? item.options.map((option, optionIndex) => ({
            localId:
              option?.localId ||
              `option-${Date.now()}-${questionIndex}-${optionIndex}`,

            option_id:
              option?.option_id ?? null,

            text:
              typeof option === "string"
                ? option
                : option?.text || "",
          }))
        : [],
    }));
  };

  /*
   * ---------------------------------------------------------
   * LOAD DASHBOARD
   * ---------------------------------------------------------
   */

  const loadDashboard = async () => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/dashboard/${dashboardId}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to load dashboard."
      );
    }

    setDashboard(data.dashboard);

    return data.dashboard;
  };

  /*
   * ---------------------------------------------------------
   * LOAD SAVED QUESTIONS
   * ---------------------------------------------------------
   *
   * Used only when Query Maker was opened directly and
   * no generatedQuestions were passed through route state.
   */

  const loadSavedQuestions = async () => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/query/questions?dashboard_id=${dashboardId}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to load questions."
      );
    }

    if (
      data.success &&
      Array.isArray(data.questions) &&
      data.questions.length
    ) {
      const formatted = normalizeQuestions(
        data.questions
      );

      setQuestions(formatted);
      setQuestionCount(formatted.length);

      return formatted;
    }

    return [];
  };

  /*
   * ---------------------------------------------------------
   * GENERATE QUESTIONS
   * ---------------------------------------------------------
   *
   * This is used only when:
   *
   * 1. User explicitly clicks Regenerate
   * OR
   * 2. Query Maker is opened directly and there are no
   *    existing questions.
   *
   * It NEVER runs automatically when route state already
   * contains generatedQuestions.
   */

  const generateQuestions = async (
    requestedCount = questionCount
  ) => {
    const safeCount = Math.min(
      MAX_QUESTIONS,
      Math.max(
        MIN_QUESTIONS,
        Number(requestedCount) || DEFAULT_QUESTIONS
      )
    );

    setGenerating(true);
    setError("");
    setSuccess("");

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/query/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            dashboard_id: Number(dashboardId),
            question_count: safeCount,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Unable to generate questions."
        );
      }

      if (
        !Array.isArray(data.questions) ||
        data.questions.length !== safeCount
      ) {
        throw new Error(
          `AI did not generate exactly ${safeCount} questions.`
        );
      }

      const formatted = normalizeQuestions(
        data.questions
      );

      setQuestions(formatted);
      setQuestionCount(formatted.length);

      setSuccess(
        `${formatted.length} questions generated successfully. Review and edit them before saving.`
      );

      return formatted;
    } catch (err) {
      console.error(
        "Question generation failed:",
        err
      );

      setError(
        err.message ||
          "Unable to generate questions."
      );

      return null;
    } finally {
      setGenerating(false);
    }
  };

  /*
   * ---------------------------------------------------------
   * INITIALIZE QUERY MAKER
   * ---------------------------------------------------------
   *
   * IMPORTANT:
   *
   * If generatedQuestions were passed from Business Info
   * or Dashboard, they are used immediately.
   *
   * We DO NOT call generateQuestions() again.
   *
   * This is the fix for the "always 4 questions" problem.
   */

  useEffect(() => {
    if (!dashboardId) {
      navigate("/dashboard", {
        replace: true,
      });

      return;
    }

    let cancelled = false;

    const initialize = async () => {
      setLoading(true);
      setError("");
      setSuccess("");

      try {
        /*
         * First load dashboard information.
         *
         * If Dashboard was already passed through route
         * state, we still refresh it from the backend so
         * the page has the latest information.
         */
        await loadDashboard();

        if (cancelled) {
          return;
        }

        /*
         * ---------------------------------------------------
         * PRIORITY 1:
         * QUESTIONS PASSED FROM BUSINESS INFO / DASHBOARD
         * ---------------------------------------------------
         */

        if (
          Array.isArray(incomingQuestions) &&
          incomingQuestions.length >= MIN_QUESTIONS &&
          incomingQuestions.length <= MAX_QUESTIONS
        ) {
          const formatted =
            normalizeQuestions(incomingQuestions);

          if (!cancelled) {
            setQuestions(formatted);
            setQuestionCount(formatted.length);

            setSuccess(
              `${formatted.length} questions generated. Review and edit them before saving.`
            );
          }

          return;
        }

        /*
         * ---------------------------------------------------
         * PRIORITY 2:
         * LOAD QUESTIONS ALREADY SAVED IN DATABASE
         * ---------------------------------------------------
         */

        const savedQuestions =
          await loadSavedQuestions();

        if (cancelled) {
          return;
        }

        if (savedQuestions.length > 0) {
          return;
        }

        /*
         * ---------------------------------------------------
         * PRIORITY 3:
         * DIRECT ENTRY WITH NO QUESTIONS
         * ---------------------------------------------------
         *
         * Only here do we generate the default questionnaire.
         *
         * Default = 4.
         */

        await generateQuestions(
          initialQuestionCount
        );
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(
          "Query Maker initialization failed:",
          err
        );

        setError(
          err.message ||
            "Unable to load questionnaire."
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    initialize();

    return () => {
      cancelled = true;
    };

    /*
     * We intentionally initialize once for the current
     * dashboard route.
     */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboardId]);

  /*
   * ---------------------------------------------------------
   * UPDATE QUESTION
   * ---------------------------------------------------------
   */

  const updateQuestion = (
    questionIndex,
    value
  ) => {
    setQuestions((current) =>
      current.map((question, index) =>
        index === questionIndex
          ? {
              ...question,
              question: value,
            }
          : question
      )
    );

    setError("");
    setSuccess("");
  };

  /*
   * ---------------------------------------------------------
   * UPDATE OPTION
   * ---------------------------------------------------------
   */

  const updateOption = (
    questionIndex,
    optionIndex,
    value
  ) => {
    setQuestions((current) =>
      current.map((question, qIndex) => {
        if (qIndex !== questionIndex) {
          return question;
        }

        return {
          ...question,

          options: question.options.map(
            (option, oIndex) =>
              oIndex === optionIndex
                ? {
                    ...option,
                    text: value,
                  }
                : option
          ),
        };
      })
    );

    setError("");
    setSuccess("");
  };

  /*
   * ---------------------------------------------------------
   * ADD OPTION
   * ---------------------------------------------------------
   */

  const addOption = (questionIndex) => {
    setQuestions((current) =>
      current.map((question, index) => {
        if (index !== questionIndex) {
          return question;
        }

        if (
          question.options.length >=
          MAX_OPTIONS
        ) {
          return question;
        }

        return {
          ...question,

          options: [
            ...question.options,

            {
              localId: `option-${Date.now()}-${Math.random()
                .toString(36)
                .slice(2)}`,

              option_id: null,

              text: "",
            },
          ],
        };
      })
    );

    setError("");
    setSuccess("");
  };

  /*
   * ---------------------------------------------------------
   * REMOVE OPTION
   * ---------------------------------------------------------
   */

  const removeOption = (
    questionIndex,
    optionIndex
  ) => {
    setQuestions((current) =>
      current.map((question, index) => {
        if (index !== questionIndex) {
          return question;
        }

        if (
          question.options.length <=
          MIN_OPTIONS
        ) {
          return question;
        }

        return {
          ...question,

          options: question.options.filter(
            (_, oIndex) =>
              oIndex !== optionIndex
          ),
        };
      })
    );

    setError("");
    setSuccess("");
  };

  /*
   * ---------------------------------------------------------
   * VALIDATE QUESTIONS
   * ---------------------------------------------------------
   */

  const validateQuestions = () => {
    if (
      questions.length < MIN_QUESTIONS ||
      questions.length > MAX_QUESTIONS
    ) {
      setError(
        `You must have between ${MIN_QUESTIONS} and ${MAX_QUESTIONS} questions.`
      );

      return false;
    }

    for (
      let i = 0;
      i < questions.length;
      i += 1
    ) {
      const question = questions[i];

      if (!question.question.trim()) {
        setError(
          `Question ${i + 1} cannot be empty.`
        );

        return false;
      }

      if (
        question.question.trim().length > 500
      ) {
        setError(
          `Question ${i + 1} cannot exceed 500 characters.`
        );

        return false;
      }

      if (
        question.options.length <
          MIN_OPTIONS ||
        question.options.length >
          MAX_OPTIONS
      ) {
        setError(
          `Question ${i + 1} must have between ${MIN_OPTIONS} and ${MAX_OPTIONS} options.`
        );

        return false;
      }

      for (
        let j = 0;
        j < question.options.length;
        j += 1
      ) {
        const option =
          question.options[j].text.trim();

        if (!option) {
          setError(
            `Option ${j + 1} in question ${i + 1} cannot be empty.`
          );

          return false;
        }

        if (option.length > 500) {
          setError(
            `Option ${j + 1} in question ${i + 1} cannot exceed 500 characters.`
          );

          return false;
        }
      }
    }

    return true;
  };

  /*
   * ---------------------------------------------------------
   * SAVE QUESTIONS
   * ---------------------------------------------------------
   */

  const handleSave = async () => {
    if (!validateQuestions()) {
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const payload = {
        dashboard_id: Number(dashboardId),

        questions: questions.map(
          (question) => ({
            question:
              question.question.trim(),

            options:
              question.options.map(
                (option) =>
                  option.text.trim()
              ),
          })
        ),
      };

      const response = await apiFetch(
        `${API_BASE_URL}/api/query/questions`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Unable to save questions."
        );
      }

      setSuccess(
        "Questions and options saved successfully."
      );

      /*
       * Return to the actual dashboard route.
       *
       * Do NOT use:
       * /dashboard/:dashboardId
       *
       * because the application route is:
       * /dashboard
       */
      setTimeout(() => {
        navigate("/dashboard", {
          replace: true,
        });
      }, 700);
    } catch (err) {
      console.error(
        "Saving questions failed:",
        err
      );

      setError(
        err.message ||
          "Unable to save questions."
      );
    } finally {
      setSaving(false);
    }
  };

  /*
   * ---------------------------------------------------------
   * LOADING SCREEN
   * ---------------------------------------------------------
   */

  if (loading) {
    return (
      <main className="query-maker-page">
        <div className="query-maker-loading">
          <div className="query-maker-spinner" />

          <p>
            Preparing your questionnaire...
          </p>
        </div>
      </main>
    );
  }

  /*
   * ---------------------------------------------------------
   * PAGE
   * ---------------------------------------------------------
   */

  return (
    <main className="query-maker-page">
      <div className="query-maker-container">

        {/* ===============================================
            TOP BAR
        =============================================== */}

        <header className="query-maker-topbar">
          <div className="query-maker-brand">
            <div className="query-maker-brand-icon">
              Q
            </div>

            <div>
              <strong>
                {dashboard?.dashboard_name ||
                  "Dashboard"}
              </strong>

              <span>
                Question Builder
              </span>
            </div>
          </div>

          <div
            className="query-maker-secure"
            aria-label="Secure"
          >
            ●
          </div>
        </header>

        {/* ===============================================
            INTRO
        =============================================== */}

        <section className="query-maker-intro">
          <span className="query-maker-kicker">
            DASHBOARD QUESTIONNAIRE
          </span>

          <h1>
            Build your
            <span> questions</span>
          </h1>

          <p>
            Create the customer questions for
            this dashboard. AI can generate them,
            and you can edit everything before
            saving.
          </p>
        </section>

        {/* ===============================================
            AI QUESTIONNAIRE CONTROLS
        =============================================== */}

        <section className="query-maker-ai-controls">
          <div className="query-maker-count-panel">
            <div className="query-maker-count-heading">
              <div>
                <span className="query-maker-control-label">
                  QUESTION COUNT
                </span>

                <strong>
                  Number of questions
                </strong>

                <p>
                  Choose how many customer questions AI should create.
                </p>
              </div>

              <div
                className="query-maker-question-count-value"
                aria-label={`${questionCount} questions selected`}
              >
                {questionCount}
              </div>
            </div>

            <div className="query-maker-slider-wrap">
              <input
                id="query-maker-question-count"
                type="range"
                min={MIN_QUESTIONS}
                max={MAX_QUESTIONS}
                step="1"
                value={questionCount}
                onChange={(event) =>
                  setQuestionCount(Number(event.target.value))
                }
                className="query-maker-question-slider"
                disabled={generating || saving}
                aria-label="Number of questions"
              />

              <div
                className="query-maker-question-scale"
                aria-hidden="true"
              >
                {[2, 3, 4, 5, 6, 7, 8].map((number) => (
                  <span key={number}>{number}</span>
                ))}
              </div>
            </div>
          </div>

          <div className="query-maker-ai-divider" />

          <div className="query-maker-regenerate-panel">
            <div className="query-maker-regenerate-copy">
              <span className="query-maker-control-label">
                AI QUESTIONNAIRE
              </span>

              <strong>
                {questions.length} questions ready
              </strong>

              <p>
                Regenerate the questionnaire using the selected count.
              </p>
            </div>

            <button
              type="button"
              className="query-maker-regenerate-button"
              onClick={() =>
                generateQuestions(
                  questionCount
                )
              }
              disabled={
                generating || saving
              }
            >
              {generating ? (
                <>
                  <span className="query-maker-button-spinner" />
                  Generating...
                </>
              ) : (
                <>
                  <span className="query-maker-regenerate-icon">
                    ↻
                  </span>
                  Regenerate
                </>
              )}
            </button>
          </div>
        </section>

        {/* ===============================================
            ERROR
        =============================================== */}

        {error && (
          <div
            className="query-maker-message error"
            role="alert"
          >
            {error}
          </div>
        )}

        {/* ===============================================
            SUCCESS
        =============================================== */}

        {success && (
          <div
            className="query-maker-message success"
          >
            {success}
          </div>
        )}

        {/* ===============================================
            QUESTION CARD
        =============================================== */}

        <section className="query-maker-card">
          {questions.length === 0 ? (
            <div className="query-maker-empty">
              <strong>
                No questions available
              </strong>

              <span>
                Generate questions to start
                building your questionnaire.
              </span>

              <button
                type="button"
                onClick={() =>
                  generateQuestions(
                    questionCount
                  )
                }
                disabled={
                  generating || saving
                }
              >
                {generating
                  ? "Generating..."
                  : "Generate Questions"}
              </button>
            </div>
          ) : (
            questions.map(
              (
                question,
                questionIndex
              ) => (
                <div
                  className="query-editor"
                  key={
                    question.localId ||
                    question.query_id ||
                    questionIndex
                  }
                >
                  {/* QUESTION HEADER */}

                  <div className="query-editor-header">
                    <div className="query-number">
                      {String(
                        questionIndex + 1
                      ).padStart(2, "0")}
                    </div>

                    <div>
                      <span>
                        QUESTION
                      </span>

                      <strong>
                        Edit question
                      </strong>
                    </div>
                  </div>

                  {/* QUESTION INPUT */}

                  <textarea
                    className="query-question-input"
                    value={
                      question.question
                    }
                    onChange={(event) =>
                      updateQuestion(
                        questionIndex,
                        event.target.value
                      )
                    }
                    maxLength={500}
                    rows={2}
                    placeholder="Enter your question..."
                    disabled={
                      saving ||
                      generating
                    }
                  />

                  {/* OPTIONS HEADER */}

                  <div className="query-options-heading">
                    <span>
                      OPTIONS
                    </span>

                    <small>
                      {
                        question.options
                          .length
                      }{" "}
                      options
                    </small>
                  </div>

                  {/* OPTIONS */}

                  <div className="query-options-list">
                    {question.options.map(
                      (
                        option,
                        optionIndex
                      ) => (
                        <div
                          className="query-option-row"
                          key={
                            option.localId ||
                            option.option_id ||
                            optionIndex
                          }
                        >
                          <div className="query-option-number">
                            {optionIndex + 1}
                          </div>

                          <input
                            type="text"
                            value={
                              option.text
                            }
                            onChange={(
                              event
                            ) =>
                              updateOption(
                                questionIndex,
                                optionIndex,
                                event.target
                                  .value
                              )
                            }
                            maxLength={500}
                            placeholder={`Option ${
                              optionIndex + 1
                            }`}
                            disabled={
                              saving ||
                              generating
                            }
                          />

                          <button
                            type="button"
                            className="query-option-remove"
                            onClick={() =>
                              removeOption(
                                questionIndex,
                                optionIndex
                              )
                            }
                            disabled={
                              saving ||
                              generating ||
                              question
                                .options
                                .length <=
                                MIN_OPTIONS
                            }
                            aria-label="Remove option"
                          >
                            ×
                          </button>
                        </div>
                      )
                    )}
                  </div>

                  {/* ADD OPTION */}

                  <button
                    type="button"
                    className="query-add-option"
                    onClick={() =>
                      addOption(
                        questionIndex
                      )
                    }
                    disabled={
                      saving ||
                      generating ||
                      question.options
                        .length >=
                        MAX_OPTIONS
                    }
                  >
                    + Add option
                  </button>

                  {/* DIVIDER */}

                  {questionIndex <
                    questions.length -
                      1 && (
                    <div className="query-divider" />
                  )}
                </div>
              )
            )
          )}
        </section>

        {/* ===============================================
            SAVE ACTION
        =============================================== */}

        <section className="query-maker-action">
          <div className="query-maker-status">
            <div className="query-maker-status-icon">
              ✓
            </div>

            <div>
              <strong>
                Ready to save
              </strong>

              <span>
                Customers will use these
                questions to create reviews.
              </span>
            </div>
          </div>

          <button
            type="button"
            className="query-save-button"
            onClick={handleSave}
            disabled={
              saving ||
              generating ||
              questions.length <
                MIN_QUESTIONS ||
              questions.length >
                MAX_QUESTIONS
            }
          >
            {saving
              ? "Saving..."
              : "Save Questions"}

            <span>→</span>
          </button>
        </section>

        {/* ===============================================
            FOOTER
        =============================================== */}

        <footer className="query-maker-footer">
          {dashboard?.dashboard_name ||
            "Dashboard"}

          <span>•</span>

          AI-generated,
          human-editable
        </footer>
      </div>
    </main>
  );
}

export default QueryMaker;