/**
 * Utilities for customer-facing URLs.
 * The slug is presentation-only; stable public IDs/tokens remain the identifiers.
 */
export function businessSlugify(value) {
  const slug = String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80)
    .replace(/-+$/g, "");

  return slug || "business";
}

export function qrLandingPath(businessName, qrToken) {
  return `/${businessSlugify(businessName)}/${encodeURIComponent(qrToken)}`;
}

export function customerDashboardPath(businessName, publicUrlId) {
  return `/${businessSlugify(businessName)}/customer-dashboard/${encodeURIComponent(publicUrlId)}`;
}

export function websitePreviewPath(businessName, publicUrlId) {
  return `/${businessSlugify(businessName)}/website-preview/${encodeURIComponent(publicUrlId)}`;
}
