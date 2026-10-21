import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/google_reviews.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function getToken() {
  return localStorage.getItem("access_token");
}

export default function GoogleReviews() {
  const navigate = useNavigate();
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [savingId, setSavingId] = useState(null);

  const apiFetch = useCallback(async (url, options = {}) => {
    const token = getToken();
    if (!token) {
      navigate("/login", { replace: true });
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
      localStorage.removeItem("access_token");
      navigate("/login", { replace: true });
      throw new Error("Your session has expired.");
    }

    return response;
  }, [navigate]);

  const loadReviews = useCallback(async () => {
    const response = await apiFetch(`${API_BASE_URL}/api/ai-review-reply/reviews`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to load reviews.");
    setReviews(Array.isArray(data.reviews) ? data.reviews : []);
  }, [apiFetch]);

  useEffect(() => {
    loadReviews()
      .catch((err) => setError(err.message || "Unable to load reviews."))
      .finally(() => setLoading(false));
  }, [loadReviews]);

  const handleSync = async () => {
    setSyncing(true);
    setError("");
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/ai-review-reply/reviews/sync`, {
        method: "POST",
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to synchronize reviews.");
      await loadReviews();
    } catch (err) {
      setError(err.message || "Unable to synchronize reviews.");
    } finally {
      setSyncing(false);
    }
  };

  const handleReply = async (reviewId) => {
    const comment = (drafts[reviewId] || "").trim();
    if (!comment) return;

    setSavingId(reviewId);
    setError("");
    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/ai-review-reply/reviews/${reviewId}/reply`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ comment }),
        }
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to publish reply.");
      await loadReviews();
      setExpandedId(null);
    } catch (err) {
      setError(err.message || "Unable to publish reply.");
    } finally {
      setSavingId(null);
    }
  };

  const handleDeleteReply = async (reviewId) => {
    setSavingId(reviewId);
    setError("");
    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/ai-review-reply/reviews/${reviewId}/reply`,
        { method: "DELETE" }
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to delete reply.");
      await loadReviews();
    } catch (err) {
      setError(err.message || "Unable to delete reply.");
    } finally {
      setSavingId(null);
    }
  };

  const averageRating = useMemo(() => {
    const values = reviews
      .map((review) => ({ FIVE: 5, FOUR: 4, THREE: 3, TWO: 2, ONE: 1 }[review.star_rating]))
      .filter(Boolean);
    if (!values.length) return "—";
    return (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
  }, [reviews]);

  return (
    <main className="google-reviews-page">
      <div className="google-reviews-shell">
        <header className="google-reviews-header">
          <button className="google-reviews-back" onClick={() => navigate("/google-business")} aria-label="Back">←</button>
          <div>
            <span className="google-reviews-kicker">GOOGLE BUSINESS PROFILE</span>
            <h1>Customer Reviews</h1>
          </div>
          <button className="google-reviews-sync" onClick={handleSync} disabled={syncing}>
            {syncing ? "Syncing…" : "Sync"}
          </button>
        </header>

        <section className="google-reviews-summary">
          <div><strong>{reviews.length}</strong><span>Reviews</span></div>
          <div><strong>{averageRating}</strong><span>Average rating</span></div>
        </section>

        {error && <div className="google-reviews-alert">{error}</div>}

        {loading ? (
          <div className="google-reviews-loading"><span />Loading Google reviews…</div>
        ) : reviews.length === 0 ? (
          <div className="google-reviews-empty">
            <strong>No reviews synced yet</strong>
            <p>Click Sync to retrieve the latest reviews from Google.</p>
          </div>
        ) : (
          <section className="google-review-list">
            {reviews.map((review) => {
              const expanded = expandedId === review.review_id;
              const stars = { FIVE: 5, FOUR: 4, THREE: 3, TWO: 2, ONE: 1 }[review.star_rating] || 0;
              return (
                <article className="google-review-card" key={review.review_id}>
                  <div className="google-review-top">
                    <div className="google-review-avatar">{(review.reviewer_name || "G").charAt(0).toUpperCase()}</div>
                    <div className="google-review-person">
                      <strong>{review.reviewer_name}</strong>
                      <span>{"★".repeat(stars)}{"☆".repeat(5 - stars)}</span>
                    </div>
                  </div>
                  <p className="google-review-comment">{review.comment || "Rating only review"}</p>
                  {review.reply_comment && (
                    <div className="google-review-existing-reply">
                      <span>Your reply</span>
                      <p>{review.reply_comment}</p>
                    </div>
                  )}
                  {expanded && (
                    <div className="google-review-editor">
                      <textarea
                        value={drafts[review.review_id] ?? review.reply_comment ?? ""}
                        onChange={(e) => setDrafts((current) => ({ ...current, [review.review_id]: e.target.value }))}
                        maxLength={4096}
                        placeholder="Write a professional reply…"
                      />
                      <div className="google-review-editor-actions">
                        <button onClick={() => setExpandedId(null)} disabled={savingId === review.review_id}>Cancel</button>
                        <button onClick={() => handleReply(review.review_id)} disabled={savingId === review.review_id || !(drafts[review.review_id] || review.reply_comment || "").trim()}>
                          {savingId === review.review_id ? "Publishing…" : review.reply_comment ? "Update reply" : "Publish reply"}
                        </button>
                      </div>
                    </div>
                  )}
                  <div className="google-review-actions">
                    <button onClick={() => { setExpandedId(review.review_id); setDrafts((current) => ({ ...current, [review.review_id]: current[review.review_id] ?? review.reply_comment ?? "" })); }}>
                      {review.reply_comment ? "Edit reply" : "Reply"}
                    </button>
                    {review.reply_comment && <button className="danger" onClick={() => handleDeleteReply(review.review_id)} disabled={savingId === review.review_id}>Delete reply</button>}
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}
