import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./business_info.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const MIN_QUESTIONS = 2;
const MAX_QUESTIONS = 8;
const DEFAULT_QUESTIONS = 4;

function BusinessInfo() {
  const navigate = useNavigate();
  const formRef = useRef(null);

  const [formData, setFormData] = useState({
    business_name: "",
    business_type: "",
    about_business: "",
    year_established: "",
    google_review_link: "",
  });

  // The backend is the single source of truth for date/time formatting.
  // Never format this timestamp in the frontend.
  const [updatedAtFormatted, setUpdatedAtFormatted] = useState("");

  const [questionCount, setQuestionCount] =
    useState(DEFAULT_QUESTIONS);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMode, setSaveMode] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // =====================================================
  // LOAD EXISTING BUSINESS INFORMATION
  // =====================================================

  useEffect(() => {
    const loadBusinessInfo = async () => {
      const token = localStorage.getItem("access_token");

      if (!token) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/business/info`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (response.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("auth_user");

          navigate("/login", { replace: true });
          return;
        }

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Unable to load business information."
          );
        }

        if (data.business_id) {
          setFormData({
            business_name: data.business_name || "",
            business_type: data.business_type || "",
            about_business: data.about_business || "",
            year_established: data.year_established
              ? String(data.year_established)
              : "",
            google_review_link:
              data.google_review_link || "",
          });

          setUpdatedAtFormatted(data.updated_at_formatted || "");
        }
      } catch (err) {
        console.error(
          "Business information loading failed:",
          err
        );

        setError(
          err.message ||
            "Unable to load business information."
        );
      } finally {
        setLoading(false);
      }
    };

    loadBusinessInfo();
  }, [navigate]);

  // =====================================================
  // HANDLE INPUT CHANGE
  // =====================================================

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((previous) => ({
      ...previous,
      [name]: value,
    }));

    setError("");
    setSuccess("");
  };

  // =====================================================
  // HANDLE QUESTION COUNT
  // =====================================================

  const handleQuestionCountChange = (event) => {
    const value = Number(event.target.value);

    const normalizedValue = Math.min(
      MAX_QUESTIONS,
      Math.max(MIN_QUESTIONS, value)
    );

    setQuestionCount(normalizedValue);

    setError("");
    setSuccess("");
  };

  // =====================================================
  // SAVE BUSINESS INFORMATION ONLY
  // =====================================================

  const handleSaveInformation = async () => {
    if (!formRef.current?.reportValidity()) {
      return;
    }

    setError("");
    setSuccess("");
    setSaving(true);
    setSaveMode("save");

    const token = localStorage.getItem("access_token");

    if (!token) {
      setSaving(false);
      setSaveMode("");
      navigate("/login", { replace: true });
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/business/info`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            business_name: formData.business_name.trim(),
            business_type: formData.business_type.trim(),
            about_business: formData.about_business.trim(),
            year_established: Number(formData.year_established),
            google_review_link:
              formData.google_review_link.trim(),
          }),
        }
      );

      if (response.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("auth_user");
        navigate("/login", { replace: true });
        return;
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to save business information."
        );
      }

      setUpdatedAtFormatted(data.updated_at_formatted || "");
      setSuccess("Business information saved successfully.");
    } catch (err) {
      console.error("Business information save failed:", err);
      setError(
        err.message || "Unable to save business information."
      );
    } finally {
      setSaving(false);
      setSaveMode("");
    }
  };

  // =====================================================
  // SUBMIT BUSINESS INFORMATION
  // =====================================================

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setSuccess("");
    setSaving(true);
    setSaveMode("continue");

    const token = localStorage.getItem("access_token");

    if (!token) {
      navigate("/login", { replace: true });
      return;
    }

    const authHeaders = {
      Authorization: `Bearer ${token}`,
    };

    /*
     * Always normalize the value before using it.
     *
     * This guarantees that:
     * 2 <= selectedQuestionCount <= 8
     *
     * and that the exact same number is used for:
     * - API request
     * - validation
     * - Query Maker route state
     */

    const selectedQuestionCount = Math.min(
      MAX_QUESTIONS,
      Math.max(
        MIN_QUESTIONS,
        Number(questionCount)
      )
    );

    // Keep track of the dashboard created during this setup.
    // If AI generation fails, it is immediately deleted so
    // the dashboard list never contains an empty dashboard.
    let createdDashboardId = null;
    let generationSucceeded = false;

    const deleteCreatedDashboard = async () => {
      if (!createdDashboardId) return;

      try {
        const deleteResponse = await fetch(
          `${API_BASE_URL}/api/dashboard/${createdDashboardId}`,
          {
            method: "DELETE",
            headers: authHeaders,
          }
        );

        if (!deleteResponse.ok) {
          console.error(
            "Automatic dashboard cleanup failed:",
            await deleteResponse.text()
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
      // ===================================================
      // STEP 1: SAVE / UPDATE BUSINESS INFORMATION
      // ===================================================

      const businessResponse = await fetch(
        `${API_BASE_URL}/api/business/info`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders,
          },
          body: JSON.stringify({
            business_name:
              formData.business_name.trim(),

            business_type:
              formData.business_type.trim(),

            about_business:
              formData.about_business.trim(),

            year_established:
              Number(formData.year_established),

            google_review_link:
              formData.google_review_link.trim(),
          }),
        }
      );

      if (businessResponse.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("auth_user");

        navigate("/login", { replace: true });
        return;
      }

      const businessData =
        await businessResponse.json();

      if (!businessResponse.ok) {
        throw new Error(
          businessData.detail ||
            "Unable to save business information."
        );
      }

      // ===================================================
      // STEP 2: LOAD EXISTING DASHBOARDS
      // ===================================================

      setSuccess(
        "Business information saved. Preparing your dashboard..."
      );

      const dashboardsResponse = await fetch(
        `${API_BASE_URL}/api/dashboard`,
        {
          method: "GET",
          headers: authHeaders,
        }
      );

      if (dashboardsResponse.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("auth_user");

        navigate("/login", { replace: true });
        return;
      }

      const dashboardsData =
        await dashboardsResponse.json();

      if (!dashboardsResponse.ok) {
        throw new Error(
          dashboardsData.detail ||
            "Unable to load your dashboards."
        );
      }

      const dashboards = Array.isArray(
        dashboardsData.dashboards
      )
        ? dashboardsData.dashboards
        : [];

      // ===================================================
      // STEP 3: CREATE A NEW UNIQUE DASHBOARD
      // ===================================================

      const existingDashboardNames =
        new Set(
          dashboards
            .map((item) =>
              String(
                item.dashboard_name || ""
              )
                .trim()
                .toLowerCase()
            )
            .filter(Boolean)
        );

      let dashboardName = "Dashboard";

      if (
        existingDashboardNames.has(
          "dashboard"
        )
      ) {
        let dashboardNumber = 2;

        while (
          existingDashboardNames.has(
            `dashboard ${dashboardNumber}`
          )
        ) {
          dashboardNumber += 1;
        }

        dashboardName =
          `Dashboard ${dashboardNumber}`;
      }

      setSuccess(
        `Creating ${dashboardName}...`
      );

      const createDashboardResponse =
        await fetch(
          `${API_BASE_URL}/api/dashboard`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...authHeaders,
            },
            body: JSON.stringify({
              dashboard_name:
                dashboardName,
            }),
          }
        );

      if (
        createDashboardResponse.status === 401
      ) {
        localStorage.removeItem(
          "access_token"
        );

        localStorage.removeItem(
          "auth_user"
        );

        navigate("/login", {
          replace: true,
        });

        return;
      }

      const createDashboardData =
        await createDashboardResponse.json();

      if (!createDashboardResponse.ok) {
        throw new Error(
          createDashboardData.detail ||
            "Unable to create a new dashboard."
        );
      }

      const dashboard =
        createDashboardData.dashboard;

      // ===================================================
      // STEP 4: VALIDATE DASHBOARD
      // ===================================================

      const dashboardId =
        dashboard?.dashboard_id;

      createdDashboardId = dashboardId;

      if (!dashboardId) {
        throw new Error(
          "The new dashboard was created, but its dashboard ID could not be determined."
        );
      }

      // ===================================================
      // STEP 5: GENERATE AI QUESTIONS
      // ===================================================

      setSuccess(
        `Creating ${selectedQuestionCount} customer questions...`
      );

      console.log(
        "Business Info question count:",
        selectedQuestionCount
      );

      const generateResponse = await fetch(
        `${API_BASE_URL}/api/query/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders,
          },
          body: JSON.stringify({
            dashboard_id: dashboardId,

            question_count:
              selectedQuestionCount,
          }),
        }
      );

      if (generateResponse.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("auth_user");

        navigate("/login", {
          replace: true,
        });

        return;
      }

      const generateData =
        await generateResponse.json();

      if (!generateResponse.ok) {
        throw new Error(
          generateData.detail ||
            "Dashboard was created, but questions could not be generated."
        );
      }

      // ===================================================
      // STEP 6: VALIDATE EXACT QUESTION COUNT
      // ===================================================

      if (
        !Array.isArray(
          generateData.questions
        )
      ) {
        throw new Error(
          "The AI response did not contain a valid questions list."
        );
      }

      if (
        generateData.questions.length !==
        selectedQuestionCount
      ) {
        throw new Error(
          `AI generated ${
            generateData.questions.length
          } questions instead of ${selectedQuestionCount}.`
        );
      }

      generationSucceeded = true;

      // ===================================================
      // STEP 7: OPEN QUERY MAKER
      // ===================================================

      navigate(
        `/query-maker/${dashboardId}`,
        {
          replace: true,

          state: {
            generatedQuestions:
              generateData.questions,

            questionCount:
              Number(
                selectedQuestionCount
              ),

            dashboardId,

            dashboard,
          },
        }
      );
    } catch (err) {
      console.error(
        "Business information setup failed:",
        err
      );

      // Never leave a dashboard with zero questions behind.
      if (createdDashboardId && !generationSucceeded) {
        await deleteCreatedDashboard();
      }

      setError(
        err.message ||
          "Unable to complete the dashboard setup. Please try again."
      );
    } finally {
      setSaving(false);
      setSaveMode("");
    }
  };


  // =====================================================
  // LOADING STATE
  // =====================================================

  if (loading) {
    return (
      <div className="business-info-page">
        <div className="business-info-loading">
          <div className="business-info-spinner" />

          <p>
            Loading your business profile...
          </p>
        </div>
      </div>
    );
  }

  // =====================================================
  // PAGE
  // =====================================================

  return (
    <main className="business-info-page">
      <div className="business-info-container">

        {/* =================================================
            TOP BAR
            ================================================= */}

        <header className="business-info-topbar">

          <div className="business-info-brand">

            <div className="business-info-brand-mark">
              <svg
                viewBox="0 0 24 24"
                fill="none"
              >
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
              <strong>
                AI Reviewer
              </strong>

              <span>
                Business Profile
              </span>
            </div>

          </div>

          <div className="business-info-secure">
            <svg
              viewBox="0 0 24 24"
              fill="none"
            >
              <path
                d="M7 10V7a5 5 0 0 1 10 0v3"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />

              <rect
                x="5"
                y="10"
                width="14"
                height="10"
                rx="2"
                stroke="currentColor"
                strokeWidth="1.8"
              />
            </svg>
          </div>

        </header>

        {/* =================================================
            PAGE INTRO
            ================================================= */}

        <section className="business-info-header">

          <div className="business-info-progress">

            <div className="business-info-progress-top">
              <span>
                BUSINESS PROFILE
              </span>

              <strong>
                1 of 1
              </strong>
            </div>

            <div className="business-info-progress-track">
              <div className="business-info-progress-fill" />
            </div>

          </div>

          <span className="business-info-kicker">
            GET STARTED
          </span>

          <h1>
            Tell us about your business
          </h1>

          <p>
            Add a few details about your
            business so AI Reviewer can create
            more relevant experiences for your
            customers.
          </p>

        </section>

        {/* =================================================
            FORM CARD
            ================================================= */}

        <section className="business-info-card">

          <div className="business-info-card-header">

            <div className="business-info-card-header-main">
              <div className="business-info-card-icon">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <path
                    d="M4 21h16M6.5 21V9.5h11V21M9 9.5V6.5h6v3"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />

                  <path
                    d="M8.5 13h1M8.5 16.5h1M14.5 13h1M14.5 16.5h1"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </div>

              <div>
                <h2>
                  Business details
                </h2>

                <p>
                  Keep your information accurate
                  and up to date.
                </p>
              </div>
            </div>

            {updatedAtFormatted && (
              <div className="business-info-updated">
                <span>Last updated</span>
                <strong>{updatedAtFormatted}</strong>
              </div>
            )}

          </div>

          <form ref={formRef} onSubmit={handleSubmit}>

            {/* =================================================
                BUSINESS NAME
                ================================================= */}

            <div className="business-info-field">

              <label htmlFor="business_name">
                Business Name
                <span className="required-mark">
                  *
                </span>
              </label>

              <div className="business-info-input-wrap">

                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <path
                    d="M4 21h16M6.5 21V9.5h11V21M9 9.5V6.5h6v3"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>

                <input
                  id="business_name"
                  name="business_name"
                  type="text"
                  placeholder="Enter your business name"
                  value={
                    formData.business_name
                  }
                  onChange={handleChange}
                  maxLength={255}
                  required
                />

              </div>

            </div>

            {/* =================================================
                BUSINESS TYPE
                ================================================= */}

            <div className="business-info-field">

              <label htmlFor="business_type">
                Business Type
                <span className="required-mark">
                  *
                </span>
              </label>

              <div className="business-info-input-wrap">

                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <path
                    d="M5 20V9h14v11M8 9V5h8v4M8 13h2M14 13h2M8 16.5h2M14 16.5h2"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>

                <input
                  id="business_type"
                  name="business_type"
                  type="text"
                  placeholder="e.g. Dental Clinic, Restaurant, Salon"
                  value={
                    formData.business_type
                  }
                  onChange={handleChange}
                  maxLength={100}
                  required
                />

              </div>

              <span className="business-info-hint">
                What type of business do you operate?
              </span>

            </div>

            {/* =================================================
                ABOUT BUSINESS
                ================================================= */}

            <div className="business-info-field">

              <div className="business-info-label-row">

                <label htmlFor="about_business">
                  About Business
                  <span className="required-mark">
                    *
                  </span>
                </label>

                <span className="business-info-counter">
                  {
                    formData.about_business
                      .length
                  }
                  /2000
                </span>

              </div>

              <div className="business-info-textarea-wrap">

                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <path
                    d="M5 5.5A2.5 2.5 0 0 1 7.5 3h9A2.5 2.5 0 0 1 19 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 18.5v-13Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />

                  <path
                    d="M8.5 8h7M8.5 12h7M8.5 16h4"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>

                <textarea
                  id="about_business"
                  name="about_business"
                  placeholder="Tell us briefly about your business, the services you provide, and what makes your business unique..."
                  value={
                    formData.about_business
                  }
                  onChange={handleChange}
                  maxLength={2000}
                  rows={5}
                  required
                />

              </div>

              <span className="business-info-hint">
                A clear description helps AI Reviewer
                understand your business better.
              </span>

            </div>

            {/* =================================================
                YEAR ESTABLISHED
                ================================================= */}

            <div className="business-info-field">

              <label htmlFor="year_established">
                Year Established
                <span className="required-mark">
                  *
                </span>
              </label>

              <div className="business-info-input-wrap">

                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <rect
                    x="4"
                    y="5"
                    width="16"
                    height="15"
                    rx="2"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />

                  <path
                    d="M8 3v4M16 3v4M4 9h16"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />

                  <path
                    d="M8 13h.01M12 13h.01M16 13h.01M8 16.5h.01M12 16.5h.01"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                  />
                </svg>

                <input
                  id="year_established"
                  name="year_established"
                  type="number"
                  placeholder="e.g. 2018"
                  value={
                    formData.year_established
                  }
                  onChange={handleChange}
                  min="1800"
                  max="2100"
                  required
                />

              </div>

            </div>

            {/* =================================================
                GOOGLE BUSINESS REVIEW LINK
                ================================================= */}

            <div className="business-info-field">
              <label htmlFor="google_review_link">
                Google Business Review Link
                <span className="required-mark">
                  *
                </span>
              </label>

              <div className="business-info-input-wrap">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />

                  <path
                    d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>

                <input
                  id="google_review_link"
                  name="google_review_link"
                  type="url"
                  inputMode="url"
                  placeholder="https://g.page/r/..."
                  value={formData.google_review_link}
                  onChange={handleChange}
                  maxLength={1000}
                  required
                />
              </div>

              <span className="business-info-hint">
                Add the Google link customers should use to leave a review.
              </span>
            </div>

            {/* =================================================
                QUESTION COUNT
                ================================================= */}

            <div className="business-info-field question-count-field">

              <div className="business-info-label-row">

                <label htmlFor="question_count">
                  Number of Questions
                  <span className="required-mark">
                    *
                  </span>
                </label>

                <span className="question-count-value">
                  {questionCount}
                </span>

              </div>

              <div className="question-slider-card">

                <div className="question-slider-header">

                  <div>
                    <strong>
                      AI Question Count
                    </strong>

                    <span>
                      Choose between 2 and 8 questions.
                    </span>
                  </div>

                  <div className="question-slider-number">
                    {questionCount}
                  </div>

                </div>

                <input
                  id="question_count"
                  name="question_count"
                  type="range"
                  min={MIN_QUESTIONS}
                  max={MAX_QUESTIONS}
                  step="1"
                  value={questionCount}
                  onChange={
                    handleQuestionCountChange
                  }
                  className="question-count-slider"
                  aria-label="Number of AI questions"
                  aria-valuemin={MIN_QUESTIONS}
                  aria-valuemax={MAX_QUESTIONS}
                  aria-valuenow={questionCount}
                />

                <div className="question-slider-scale">
                  <span>2</span>
                  <span>3</span>
                  <span>4</span>
                  <span>5</span>
                  <span>6</span>
                  <span>7</span>
                  <span>8</span>
                </div>

                <p className="business-info-hint">
                  AI will generate{" "}
                  <strong>
                    {questionCount}
                  </strong>{" "}
                  customer questions with
                  relevant options for each
                  question.
                </p>

              </div>

            </div>

            {/* =================================================
                ERROR
                ================================================= */}

            {error && (
              <div
                className="business-info-message error"
                role="alert"
              >
                <span className="business-info-message-icon">
                  !
                </span>

                <span>
                  {error}
                </span>
              </div>
            )}

            {/* =================================================
                SUCCESS
                ================================================= */}

            {success && (
              <div
                className="business-info-message success"
                role="status"
              >
                <span className="business-info-message-icon">
                  ✓
                </span>

                <span>
                  {success}
                </span>
              </div>
            )}

            {/* =================================================
                SUBMIT
                ================================================= */}

            <div className="business-info-actions">

              <button
                type="button"
                className="business-info-save-button"
                onClick={handleSaveInformation}
                disabled={saving}
              >
                {saving && saveMode === "save" ? (
                  <>
                    <span className="business-info-button-spinner business-info-button-spinner-dark" />
                    Saving...
                  </>
                ) : (
                  <>
                    Save Information
                  </>
                )}
              </button>

              <button
                type="submit"
                className="business-info-submit"
                disabled={saving}
              >
              {saving ? (
                <>
                  <span className="business-info-button-spinner" />

                  Creating your questions...
                </>
              ) : (
                <>
                  Continue to Make Options

                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <path
                      d="M5 12h13M13 6l6 6-6 6"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </>
              )}
              </button>

            </div>

            <p className="business-info-footer-text">
              Your business information can be
              updated later.
            </p>

          </form>

        </section>

        {/* =================================================
            SECURITY NOTE
            ================================================= */}

        <div className="business-info-bottom-note">

          <svg
            viewBox="0 0 24 24"
            fill="none"
          >
            <path
              d="M12 3.5 4.5 7.2v5.6c0 4.2 2.9 6.8 7.5 8.1 4.6-1.3 7.5-3.9 7.5-8.1V7.2L12 3.5Z"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinejoin="round"
            />

            <path
              d="m8.5 12.1 2.2 2.2 4.8-5"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <span>
            Your information is securely handled.
          </span>

        </div>

      </div>
    </main>
  );
}

export default BusinessInfo;