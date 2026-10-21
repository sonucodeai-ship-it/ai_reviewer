import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "./review_page.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;


// =========================================================
// GOOGLE REVIEW URL
// =========================================================




// =========================================================
// CLIPBOARD HELPER
// =========================================================

const copyTextToClipboard = async (text) => {
  const cleanText = text?.trim();

  if (!cleanText) {
    throw new Error("There is no review to copy.");
  }

  // Modern browsers
  if (
    navigator.clipboard &&
    typeof navigator.clipboard.writeText === "function"
  ) {
    await navigator.clipboard.writeText(cleanText);
    return true;
  }

  // Fallback for older browsers
  const textarea = document.createElement("textarea");

  textarea.value = cleanText;

  textarea.setAttribute("readonly", "");

  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";

  document.body.appendChild(textarea);

  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(
    0,
    textarea.value.length
  );

  const copied = document.execCommand("copy");

  document.body.removeChild(textarea);

  if (!copied) {
    throw new Error("Clipboard copy failed.");
  }

  return true;
};


// =========================================================
// REVIEW PAGE
// =========================================================

function ReviewPage() {
  const location = useLocation();
  const navigate = useNavigate();


  // =======================================================
  // DYNAMIC DATA FROM DASHBOARD
  // =======================================================

  const {
    review: initialReview,
    reviewId: initialReviewId = null,
    answers: initialAnswers = [],
    dashboard: initialDashboard = null,
  } = location.state || {};

  const googleReviewUrl =
    initialDashboard?.google_review_link?.trim() || "";


  // =======================================================
  // STATE
  // =======================================================

  const [review, setReview] = useState(
    initialReview || ""
  );

  const [reviewId, setReviewId] = useState(
    initialReviewId || null
  );

  const [answers] = useState(
    Array.isArray(initialAnswers)
      ? initialAnswers
      : []
  );

  const [isEditing, setIsEditing] = useState(false);

  const [copied, setCopied] = useState(false);

  const [isRegenerating, setIsRegenerating] =
    useState(false);

  const [isOpeningGoogle, setIsOpeningGoogle] =
    useState(false);

  const [error, setError] = useState("");


  // =======================================================
  // COPIED STATE
  // =======================================================

  const showCopiedState = (
    duration = 2500
  ) => {
    setCopied(true);

    window.setTimeout(() => {
      setCopied(false);
    }, duration);
  };


  // =======================================================
  // COPY REVIEW
  // =======================================================

  const copyReviewToClipboard = async () => {
    const reviewText = review.trim();

    if (!reviewText) {
      throw new Error(
        "There is no review to copy."
      );
    }

    await copyTextToClipboard(reviewText);

    showCopiedState();
  };


  // =======================================================
  // MANUAL COPY
  // =======================================================

  const handleCopy = async () => {
    if (!review.trim()) {
      setError(
        "There is no review to copy."
      );

      return;
    }

    try {
      setError("");

      await copyReviewToClipboard();

    } catch (copyError) {
      console.error(
        "Unable to copy review:",
        copyError
      );

      setError(
        "Unable to copy the review automatically. Please copy it manually."
      );
    }
  };


  // =======================================================
  // REGENERATE REVIEW
  // =======================================================

  const handleRegenerate = async () => {
    /*
     * Regeneration requires the same answers that were
     * originally selected on the Dashboard.
     */

    if (
      isRegenerating ||
      !Array.isArray(answers) ||
      answers.length === 0
    ) {
      setError(
        "Your selected answers are not available. Please generate the review again from the Dashboard."
      );

      return;
    }

    setIsRegenerating(true);
    setError("");
    setCopied(false);

    try {
      // Customer review regeneration is intentionally public.
      // Do not require or send the business owner's authentication token.
      const response = await fetch(
        `${API_BASE_URL}/api/reviews/generate`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            answers,
            dashboard_id: initialDashboard?.dashboard_id || null,
            regenerate_status: 1,
          }),
        }
      );


      // ---------------------------------------------------
      // Parse response
      // ---------------------------------------------------

      const data =
        await response.json();


      if (!response.ok) {
        throw new Error(
          data.detail ||
          `Request failed with status ${response.status}`
        );
      }


      if (
        !data.success ||
        !data.review
      ) {
        throw new Error(
          "Invalid review response from server."
        );
      }


      // ---------------------------------------------------
      // Update displayed review
      // ---------------------------------------------------

      setReview(
        data.review
      );

      if (data.review_id) {
        setReviewId(data.review_id);
      }

      setIsEditing(false);

      setCopied(false);

    } catch (regenerateError) {
      console.error(
        "Review regeneration failed:",
        regenerateError
      );

      setError(
        regenerateError.message ||
        "Unable to regenerate the review. Please try again."
      );

    } finally {
      setIsRegenerating(false);
    }
  };


  // =======================================================
  // SAVE SUBMIT STATUS
  // =======================================================

  const saveSubmitStatus = async (status) => {
    if (!reviewId) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/reviews/${reviewId}/submit-status`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            submit_status: status,
            review_text: review.trim(),
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          data.detail || "Unable to save review submit status."
        );
      }
    } catch (statusError) {
      console.error(
        "Review submit status update failed:",
        statusError
      );
    }
  };


  // =======================================================
  // GOOGLE REVIEW
  // =======================================================

  const handleGoogleReview = async () => {
    const reviewText = review.trim();

    if (!reviewText) {
      setError(
        "Please generate a review before continuing to Google."
      );
      return;
    }

    if (!googleReviewUrl) {
      setError(
        "The Google Business Review link is not available. Please contact the business."
      );
      return;
    }

    if (isOpeningGoogle) {
      return;
    }

    setIsOpeningGoogle(true);
    setError("");

    /*
     * IMPORTANT:
     * Open Google synchronously from the user's click.
     * This gives the browser the best chance of allowing the popup.
     *
     * The returned window object is the only reliable signal available
     * to this application for determining whether the browser allowed
     * the Google window to open.
     */
    const googleWindow = window.open(
      googleReviewUrl,
      "_blank"
    );

    /*
     * Determine the Google hand-off status independently from clipboard
     * operations. Clipboard permission can fail even when Google opens
     * successfully, so it must never change the Google-open status.
     */
    if (!googleWindow) {
      await saveSubmitStatus(0);

      setError(
        "Google could not be opened. Please allow pop-ups and try again."
      );

      setIsOpeningGoogle(false);
      return;
    }

    /*
     * Google was successfully opened.
     *
     * IMPORTANT:
     * submit_status = 1 means the customer was successfully handed off
     * to Google. It does NOT mean that Google confirmed a review was
     * actually submitted. Google is a separate cross-origin website and
     * this application cannot verify the final submission from here.
     */
    await saveSubmitStatus(1);

    /*
     * Clipboard handling is intentionally independent from the Google
     * hand-off status. If copying fails, Google is already open and the
     * customer can still paste the review manually.
     */
    try {
      await copyTextToClipboard(reviewText);

      showCopiedState(3500);

      /*
       * We intentionally do not access or modify Google's page.
       */
      window.setTimeout(() => {
        setError("");
      }, 500);

    } catch (copyError) {
      console.error(
        "Unable to copy review automatically:",
        copyError
      );

      setError(
        "Google is open. The review could not be copied automatically. Please copy it manually and paste it into the review box."
      );
    } finally {
      setIsOpeningGoogle(false);
    }
  };


  // =======================================================
  // NO REVIEW STATE
  // =======================================================

  if (!initialReview) {
    return (
      <div className="review-generator-page">

        <main className="review-generator-container">

          <section className="review-main-card">

            <div className="card-top">

              <div className="ai-title">

                <div className="ai-icon">
                  !
                </div>

                <div>
                  <h3>
                    Review not found
                  </h3>

                  <span>
                    Please generate a review first.
                  </span>
                </div>

              </div>

            </div>


            <div className="review-text-box">

              <p>
                Your review session could not
                be found. Please go back and
                complete your experience details.
              </p>

            </div>


            <div className="review-actions">

              <button
                type="button"
                className="copy-button"
                onClick={() => {
                  const publicUrlId =
                    initialDashboard?.public_url_id;

                  if (publicUrlId) {
                    navigate(
                      `/customer-dashboard/${publicUrlId}`,
                      { replace: true }
                    );
                    return;
                  }

                  navigate(-1);
                }}
              >
                ← Back to Dashboard
              </button>

            </div>

          </section>

        </main>

      </div>
    );
  }


  // =======================================================
  // MAIN PAGE
  // =======================================================

  return (
    <div className="review-generator-page">

      {/* Background decorations */}

      <div className="review-bg-circle review-circle-one"></div>

      <div className="review-bg-circle review-circle-two"></div>


      <main className="review-generator-container">


        {/* =================================================
            HEADER
        ================================================= */}

        <header className="review-page-header">

          <div className="review-brand">

            <div className="review-logo">
              AI
            </div>

            <div>
              <h1>
                AI Reviewer
              </h1>

              <span>
                Customer Experience
              </span>
            </div>

          </div>


          <div className="secure-badge">

            <span className="secure-icon">
              ✓
            </span>

            Your experience

          </div>

        </header>


        {/* =================================================
            PROGRESS
        ================================================= */}

        <div className="progress-wrapper">

          <div className="progress-step completed">

            <div className="progress-circle">
              ✓
            </div>

            <span>
              Your Experience
            </span>

          </div>


          <div className="progress-line active"></div>


          <div className="progress-step current">

            <div className="progress-circle">
              2
            </div>

            <span>
              Review
            </span>

          </div>


          <div className="progress-line"></div>


          <div className="progress-step">

            <div className="progress-circle">
              3
            </div>

            <span>
              Google
            </span>

          </div>

        </div>


        {/* =================================================
            INTRO
        ================================================= */}

        <section className="review-intro">

          <span className="review-eyebrow">
            AI REVIEW ASSISTANT
          </span>

          <h2>
            Here's your
            <span> review</span>
          </h2>

          <p>
            We've turned your experience into
            a natural review. Feel free to edit
            it before sharing.
          </p>

        </section>


        {/* =================================================
            ERROR
        ================================================= */}

        {error && (
          <div
            className="error-message"
            role="alert"
          >
            {error}
          </div>
        )}


        {/* =================================================
            MAIN CONTENT
        ================================================= */}

        <section className="review-content">


          {/* =================================================
              AI REVIEW CARD
          ================================================= */}

          <div className="review-main-card">


            {/* Card header */}

            <div className="card-top">

              <div className="ai-title">

                <div className="ai-icon">
                  ✦
                </div>

                <div>

                  <h3>
                    AI-generated review
                  </h3>

                  <span>
                    Based on your experience
                  </span>

                </div>

              </div>


              <div className="generated-badge">

                <span></span>

                Generated

              </div>

            </div>


            {/* Rating */}

            <div className="rating-row">

              <div className="stars">
                ★★★★★
              </div>

              <span>
                Share your experience
              </span>

            </div>


            {/* Review text */}

            <div
              className={`review-text-box ${
                isEditing
                  ? "editing"
                  : ""
              }`}
            >

              {isEditing ? (

                <textarea
                  value={review}
                  onChange={(event) => {
                    setReview(
                      event.target.value
                    );

                    setCopied(false);

                    setError("");
                  }}
                  autoFocus
                  aria-label="Edit your review"
                />

              ) : (

                <p>
                  {review}
                </p>

              )}

            </div>


            {/* Review meta */}

            <div className="review-meta">

              <span>
                {review.length} characters
              </span>

              <span className="meta-dot">
                •
              </span>

              <span>
                Natural & personal
              </span>

            </div>


            {/* =================================================
                GOOGLE CTA
            ================================================= */}

            <div className="google-review-card">

              <div className="google-review-info">

                <div className="google-icon">
                  G
                </div>

                <div>

                  <strong>
                    Ready to share?
                  </strong>

                  <span>
                    Your review will be copied
                    as Google opens.
                  </span>

                </div>

              </div>


              <button
                type="button"
                className="google-button"
                onClick={
                  handleGoogleReview
                }
                disabled={
                  isOpeningGoogle ||
                  !googleReviewUrl
                }
              >

                <span>
                  {isOpeningGoogle
                    ? "Opening Google..."
                    : googleReviewUrl
                      ? "Copy & Continue to Google"
                      : "Google Review Link Unavailable"}
                </span>

                <span className="google-arrow">
                  {isOpeningGoogle
                    ? "..."
                    : "→"}
                </span>

              </button>

            </div>


            {/* =================================================
                SECONDARY ACTIONS
            ================================================= */}

            <div className="review-actions">

              {/* Edit */}

              <button
                type="button"
                className="secondary-button"
                onClick={() => {

                  setIsEditing(
                    (current) =>
                      !current
                  );

                  setError("");

                }}
              >

                <span>
                  {isEditing
                    ? "✓"
                    : "✎"}
                </span>

                {isEditing
                  ? "Save Changes"
                  : "Edit Review"}

              </button>


              {/* Regenerate */}

              <button
                type="button"
                className={`secondary-button ${
                  isRegenerating
                    ? "loading"
                    : ""
                }`}
                onClick={
                  handleRegenerate
                }
                disabled={
                  isRegenerating ||
                  answers.length === 0
                }
              >

                <span
                  className={
                    isRegenerating
                      ? "spin"
                      : ""
                  }
                >
                  ↻
                </span>

                {isRegenerating
                  ? "Generating..."
                  : "Regenerate"}

              </button>


              {/* Copy */}

              <button
                type="button"
                className="copy-button"
                onClick={
                  handleCopy
                }
              >

                <span>
                  {copied
                    ? "✓"
                    : "▣"}
                </span>

                {copied
                  ? "Copied!"
                  : "Copy Review"}

              </button>

            </div>

          </div>


          {/* =================================================
              DYNAMIC EXPERIENCE SUMMARY
          ================================================= */}

          <aside className="experience-summary">


            {/* Summary header */}

            <div className="summary-header">

              <div>

                <span className="summary-eyebrow">
                  YOUR INPUT
                </span>

                <h3>
                  Experience summary
                </h3>

              </div>

              <div className="summary-check">
                ✓
              </div>

            </div>


            {/* =================================================
                DYNAMIC QUESTIONS
            ================================================= */}

            {answers.length > 0 ? (

              answers.map(
                (answer, index) => {

                  const question =
                    answer?.question ||
                    `Question ${index + 1}`;

                  const selectedOptions =
                    Array.isArray(
                      answer?.selected_options
                    )
                      ? answer.selected_options
                      : [];


                  return (

                    <div
                      className="summary-item experience-summary-item"
                      key={
                        answer?.query_id ??
                        `answer-${index}`
                      }
                    >

                      {/* Dynamic icon */}

                      <div className="summary-icon">
                        {index + 1}
                      </div>


                      <div className="summary-detail">

                        {/* Question */}

                        <span>
                          {question}
                        </span>


                        {/* Selected options */}

                        <div className="tag-list">

                          {selectedOptions.length >
                          0 ? (

                            selectedOptions.map(
                              (
                                option,
                                optionIndex
                              ) => (

                                <span
                                  key={`${index}-${optionIndex}`}
                                  className="experience-tag"
                                >
                                  {option}
                                </span>

                              )
                            )

                          ) : (

                            <span className="experience-tag">
                              No option selected
                            </span>

                          )}

                        </div>

                      </div>

                    </div>

                  );
                }
              )

            ) : (

              <div className="summary-item">

                <div className="summary-icon">
                  !
                </div>

                <div className="summary-detail">

                  <span>
                    EXPERIENCE
                  </span>

                  <strong>
                    No selected answers available.
                  </strong>

                </div>

              </div>

            )}


            {/* Divider */}

            <div className="summary-divider"></div>


            {/* AI note */}

            <div className="ai-note">

              <div className="note-icon">
                ✦
              </div>

              <div>

                <strong>
                  Made from your answers
                </strong>

                <p>
                  Your review reflects the
                  experience you selected.
                </p>

              </div>

            </div>

          </aside>

        </section>


        {/* =================================================
            FOOTER
        ================================================= */}

        <footer className="review-footer">

          <span>
            AI Reviewer
          </span>

          <span>
            •
          </span>

          <span>
            Thank you for sharing your experience
          </span>

        </footer>

      </main>

    </div>
  );
}


export default ReviewPage;
