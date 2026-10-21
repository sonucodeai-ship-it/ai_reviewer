import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { businessSlugify, websitePreviewPath } from "../qr/publicUrl";

import "./website_preview.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function WebsitePreview() {
  const { publicUrlId, businessSlug } = useParams();
  const navigate = useNavigate();

  const [website, setWebsite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    const loadPublicWebsite = async () => {
      const id = String(publicUrlId || "").trim();

      if (!id || id === "undefined" || id === "null") {
        if (isMounted) {
          setError("Invalid website URL.");
          setLoading(false);
        }
        return;
      }

      try {
        setLoading(true);
        setError("");

        /*
         * IMPORTANT:
         *
         * This is a PUBLIC endpoint.
         * No JWT token.
         * No Authorization header.
         *
         * Anyone who has the public URL can open the website.
         */
        const response = await fetch(
          `${API_BASE_URL}/api/your-website/public/${encodeURIComponent(id)}`,
          {
            method: "GET",
            headers: {
              Accept: "application/json",
            },
          }
        );

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(
            data.detail || "Unable to load this website."
          );
        }

        const htmlCode = String(data.html_code || "").trim();

        if (!htmlCode) {
          throw new Error(
            "This website has not been published yet."
          );
        }

        if (isMounted) {
          setWebsite({
            ...data,
            html_code: htmlCode,
          });

          // The slug is cosmetic; the stable public ID resolves the website.
          // Redirect stale/legacy links to the latest business-name slug.
          const businessName = data.business?.business_name || data.business_name || "Business";
          const canonicalPath = websitePreviewPath(businessName, id);
          if (businessSlug !== businessSlugify(businessName) || window.location.pathname !== canonicalPath) {
            navigate(canonicalPath, { replace: true });
          }
        }
      } catch (error) {
        console.error(
          "Public website loading error:",
          error
        );

        if (isMounted) {
          setError(
            error.message ||
              "Unable to load this website."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadPublicWebsite();

    return () => {
      isMounted = false;
    };
  }, [publicUrlId, businessSlug, navigate]);

  /*
   * Loading state
   */
  if (loading) {
    return (
      <main className="generated-site-loading">
        <div className="generated-site-loading-card">
          <div className="generated-site-spinner" />

          <p>Loading website...</p>
        </div>
      </main>
    );
  }

  /*
   * Error state
   */
  if (error || !website?.html_code) {
    return (
      <main className="generated-site-error">
        <div className="generated-site-error-card">
          <div className="generated-site-error-icon">
            !
          </div>

          <span className="generated-site-error-label">
            WEBSITE
          </span>

          <h1>
            Website unavailable
          </h1>

          <p>
            {error ||
              "This website could not be loaded."}
          </p>
        </div>
      </main>
    );
  }

  /*
   * PUBLIC CUSTOMER WEBSITE
   *
   * The generated HTML is rendered directly
   * inside the iframe.
   */
  return (
    <main className="generated-site-shell">
      <iframe
        title={
          website.business?.business_name ||
          "Business website"
        }
        className="generated-site-frame"
        srcDoc={website.html_code}
        sandbox="allow-scripts allow-forms allow-popups allow-modals"
        referrerPolicy="no-referrer"
      />
    </main>
  );
}

export default WebsitePreview;