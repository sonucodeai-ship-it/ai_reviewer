import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./first_page.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/* =========================================================
   QUESTION OPTIONS
   ========================================================= */

const FACILITIES = [
  "Root Canal Treatment/ RCT",
  "Cleaning / Scaling",
  "Tooth Filling",
  "Tooth Extraction",
  "Braces / Ortho Treatment",
  "Dental Implant",
  "Crown / Cap",
  "Denture",
  "Child Dental Care",
  "Dental Consultation",
];

const DOCTORS = [
  "Dr. Bharti Vats",
];

const EXPERIENCES = [
  "Friendly & welcoming",
  "Clean & hygienic",
  "Doctor explained things clearly",
  "Doctor was patient & supportive",
  "Smooth & well organised",
  "Comfortable clinic environment",
];

const EXPERIENCE_ICONS = {
  "Friendly & welcoming": "♡",
  "Clean & hygienic": "✦",
  "Doctor explained things clearly": "◉",
  "Doctor was patient & supportive": "☺",
  "Smooth & well organised": "✓",
  "Comfortable clinic environment": "☼",
};

const OVERALL_EXPERIENCES = [
  "Really happy with my experience",
  "Very comfortable throughout",
  "Good overall experience",
  "Satisfied with the treatment",
  "Felt well cared for",
  "Would be happy to visit again",
];

const OVERALL_ICONS = {
  "Really happy with my experience": "★",
  "Very comfortable throughout": "☺",
  "Good overall experience": "✓",
  "Satisfied with the treatment": "♥",
  "Felt well cared for": "♡",
  "Would be happy to visit again": "↻",
};

/* =========================================================
   COMPONENT
   ========================================================= */

function FirstPage() {
  const navigate = useNavigate();

  /* ---------------------------------------------------------
     Multi-select state
  --------------------------------------------------------- */

  const [facilities, setFacilities] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [clinicExperience, setClinicExperience] = useState([]);
  const [overallExperience, setOverallExperience] = useState([]);

  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  /* ---------------------------------------------------------
     Check whether all four questions have at least one
     selected option
  --------------------------------------------------------- */

  const isComplete =
    facilities.length > 0 &&
    doctors.length > 0 &&
    clinicExperience.length > 0 &&
    overallExperience.length > 0;

  /* =========================================================
     GENERIC MULTI-SELECT HANDLER
     ========================================================= */

  const toggleSelection = (value, setter) => {
    setError("");

    setter((current) => {
      if (current.includes(value)) {
        return current.filter((item) => item !== value);
      }

      return [...current, value];
    });
  };

  /* =========================================================
     CONTINUE / GENERATE REVIEW
     ========================================================= */

  const handleContinue = async () => {
    if (!isComplete || isGenerating) {
      return;
    }

    setIsGenerating(true);
    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/reviews/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            facilities,
            doctors,
            clinic_experience: clinicExperience,
            overall_experience: overallExperience,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Request failed with status ${response.status}`
        );
      }

      const data = await response.json();

      if (!data.success || !data.review) {
        throw new Error("Invalid review response from server.");
      }

      navigate("/review", {
        state: {
          review: data.review,
          facilities,
          doctors,
          clinicExperience,
          overallExperience,
        },
      });
    } catch (requestError) {
      console.error(
        "Review generation failed:",
        requestError
      );

      setError(
        "Unable to generate your review. Please make sure the backend is running and try again."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  /* =========================================================
     UI
     ========================================================= */

  return (
    <div className="review-page">

      {/* Background decoration */}
      <div className="background-circle circle-one"></div>
      <div className="background-circle circle-two"></div>

      <main className="review-container">

        {/* ===================================================
            HEADER
        =================================================== */}

        <header className="clinic-header">

          <div className="clinic-logo">

            <div className="logo-icon">
              M
            </div>

            <div className="clinic-name">
              <h1>Madhu Dentocare</h1>
              <span>Dental Clinic</span>
            </div>

          </div>

          <div className="header-badge">
            <span className="badge-dot"></span>
            User Experience
          </div>

        </header>

        {/* ===================================================
            INTRO
        =================================================== */}

        <section className="intro-section">

          <span className="eyebrow">
            YOUR EXPERIENCE MATTERS
          </span>

          <h2>
            Tell us about your
            <span> experience</span>
          </h2>

          <p>
            Answer a few simple questions about your visit.
            We'll use your answers to help create your review.
          </p>

        </section>

        {/* ===================================================
            QUESTIONS
        =================================================== */}

        <section className="questions-card">

          {/* =================================================
              QUESTION 1
          ================================================= */}

          <div className="question-section">

            <div className="question-heading">

              <div className="question-number">
                01
              </div>

              <div>
                <h3>
                  Which facility did you take?
                </h3>

                <p>
                  Select all the treatments you received.
                </p>
              </div>

            </div>

            <div className="options-grid">

              {FACILITIES.map((item) => {

                const isSelected =
                  facilities.includes(item);

                return (
                  <button
                    key={item}
                    type="button"
                    className={`option-card ${
                      isSelected ? "selected" : ""
                    }`}
                    onClick={() =>
                      toggleSelection(
                        item,
                        setFacilities
                      )
                    }
                    disabled={isGenerating}
                  >

                    <span className="option-icon">
                      +
                    </span>

                    <span>
                      {item}
                    </span>

                    <span className="selection-check">
                      ✓
                    </span>

                  </button>
                );
              })}

            </div>

          </div>

          <div className="divider"></div>

          {/* =================================================
              QUESTION 2
          ================================================= */}

          <div className="question-section">

            <div className="question-heading">

              <div className="question-number">
                02
              </div>

              <div>
                <h3>
                  Which doctor treated you?
                </h3>

                <p>
                  Select all doctors involved in your treatment.
                </p>
              </div>

            </div>

            <div className="doctor-grid">

              {DOCTORS.map((item) => {

                const isSelected =
                  doctors.includes(item);

                return (
                  <button
                    key={item}
                    type="button"
                    className={`doctor-card ${
                      isSelected ? "selected" : ""
                    }`}
                    onClick={() =>
                      toggleSelection(
                        item,
                        setDoctors
                      )
                    }
                    disabled={isGenerating}
                  >

                    <div className="doctor-avatar">
                      {item
                        .replace("Dr. ", "")
                        .charAt(0)}
                    </div>

                    <div className="doctor-info">

                      <span className="doctor-label">
                        DENTIST
                      </span>

                      <strong>
                        {item}
                      </strong>

                    </div>

                    <span className="selection-check">
                      ✓
                    </span>

                  </button>
                );
              })}

            </div>

          </div>

          <div className="divider"></div>

          {/* =================================================
              QUESTION 3
          ================================================= */}

          <div className="question-section">

            <div className="question-heading">

              <div className="question-number">
                03
              </div>

              <div>
                <h3>
                  How did you like the clinic?
                </h3>

                <p>
                  Select everything that describes your
                  experience.
                </p>
              </div>

            </div>

            <div className="experience-grid">

              {EXPERIENCES.map((item) => {

                const isSelected =
                  clinicExperience.includes(item);

                return (
                  <button
                    key={item}
                    type="button"
                    className={`experience-card ${
                      isSelected ? "selected" : ""
                    }`}
                    onClick={() =>
                      toggleSelection(
                        item,
                        setClinicExperience
                      )
                    }
                    disabled={isGenerating}
                  >

                    <span className="experience-icon">
                      {EXPERIENCE_ICONS[item]}
                    </span>

                    <span>
                      {item}
                    </span>

                    <span className="selection-check">
                      ✓
                    </span>

                  </button>
                );
              })}

            </div>

          </div>

          <div className="divider"></div>

          {/* =================================================
              QUESTION 4
          ================================================= */}

          <div className="question-section">

            <div className="question-heading">

              <div className="question-number">
                04
              </div>

              <div>
                <h3>
                  How was your overall experience?
                </h3>

                <p>
                  Select everything that best describes
                  how you felt about your visit.
                </p>
              </div>

            </div>

            <div className="overall-experience-grid">

              {OVERALL_EXPERIENCES.map((item) => {

                const isSelected =
                  overallExperience.includes(item);

                return (
                  <button
                    key={item}
                    type="button"
                    className={`overall-experience-card ${
                      isSelected ? "selected" : ""
                    }`}
                    onClick={() =>
                      toggleSelection(
                        item,
                        setOverallExperience
                      )
                    }
                    disabled={isGenerating}
                  >

                    <span className="overall-icon">
                      {OVERALL_ICONS[item]}
                    </span>

                    <span>
                      {item}
                    </span>

                    <span className="selection-check">
                      ✓
                    </span>

                  </button>
                );
              })}

            </div>

          </div>

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
              ACTION
          ================================================= */}

          <div className="action-section">

            <div className="selection-status">

              <div className="status-icon">
                {isComplete ? "✓" : "!"}
              </div>

              <div>

                <strong>
                  {isComplete
                    ? "Ready to generate"
                    : "Almost there"}
                </strong>

                <span>
                  {isComplete
                    ? "Your selections are ready."
                    : "Select your experience above to continue."}
                </span>

              </div>

            </div>

            <button
              type="button"
              className="continue-button"
              disabled={!isComplete || isGenerating}
              onClick={handleContinue}
            >

              <span>
                {isGenerating
                  ? "Generating..."
                  : "Generate Review"}
              </span>

              <span className="arrow">
                {isGenerating ? "..." : "→"}
              </span>

            </button>

          </div>

        </section>

        {/* ===================================================
            FOOTER
        =================================================== */}

        <footer className="page-footer">

          <span>
            Madhu Dentocare Clinic
          </span>

          <span className="footer-dot">
            •
          </span>

          <span>
            Your feedback helps us improve
          </span>

        </footer>

      </main>
    </div>
  );
}

export default FirstPage;