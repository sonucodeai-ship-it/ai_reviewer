"""
Professional Unsplash image-search service for the business customer showcase builder.

Responsibilities:
    1. Receive AI-generated visual search instructions.
    2. Search Unsplash from the backend using the private Access Key.
    3. Prefer clean product/object/detail photography over generic stock scenes.
    4. Return provider-supplied image URLs and attribution metadata.
    5. Never expose the Unsplash Access Key to the browser.

IMPORTANT:
    Unsplash does NOT provide a transparent-background/PNG guarantee.
    Therefore this service searches for clean, studio-style, isolated-looking
    photography rather than pretending that photographs are backgroundless.

SVG icons/decorations are intentionally NOT handled here.
The website_builder prompt should create those as inline SVG/CSS graphics.
"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


UNSPLASH_API_URL = "https://api.unsplash.com/search/photos"
UNSPLASH_TIMEOUT_SECONDS = 15

UNSPLASH_APP_NAME = os.getenv(
    "UNSPLASH_APP_NAME",
    "business_website_generator",
).strip()


# ---------------------------------------------------------------------------
# Environment / helpers
# ---------------------------------------------------------------------------

def _get_access_key() -> str:
    """Get the private Unsplash Access Key from the backend environment."""

    access_key = os.getenv(
        "UNSPLASH_ACCESS_KEY",
        "",
    ).strip()

    if not access_key:
        raise RuntimeError(
            "UNSPLASH_ACCESS_KEY is not configured. "
            "Add UNSPLASH_ACCESS_KEY to the backend .env file."
        )

    return access_key


def _safe_text(value) -> str:
    """Convert a value into a clean string."""

    return str(value or "").strip()


def _normalise_orientation(value: str) -> str:
    """Convert our UI-friendly square value to Unsplash's squarish value."""

    value = _safe_text(value).lower()

    if value == "square":
        return "squarish"

    if value not in {
        "landscape",
        "portrait",
        "squarish",
    }:
        return "landscape"

    return value


def _add_attribution_parameters(url: str) -> str:
    """
    Add the required Unsplash referral parameters to Unsplash page/profile URLs.

    The image URL itself is returned exactly as supplied by Unsplash.
    """

    url = _safe_text(url)

    if not url:
        return ""

    separator = "&" if "?" in url else "?"

    return (
        f"{url}"
        f"{separator}"
        f"utm_source={quote_plus(UNSPLASH_APP_NAME)}"
        f"&utm_medium=referral"
    )


# ---------------------------------------------------------------------------
# Search-query strategy
# ---------------------------------------------------------------------------

def _build_visual_search_queries(
    query: str,
    visual_role: str = "object",
) -> list[str]:
    """
    Create several search variants from one AI-generated visual request.

    We deliberately bias searches toward:
        - studio photography
        - clean background
        - isolated-looking objects
        - product/detail photography

    We do NOT claim that Unsplash results are transparent PNGs.
    """

    query = _safe_text(query)
    role = _safe_text(visual_role).lower()

    if not query:
        return []

    variants = []

    # The first query remains closest to the AI's intended subject.
    variants.append(query)

    if role in {
        "object",
        "product",
        "instrument",
        "equipment",
        "tool",
        "ingredient",
        "material",
        "detail",
        "supporting",
    }:
        variants.extend(
            [
                f"{query} studio product photography",
                f"{query} isolated clean background",
                f"{query} white background professional photography",
            ]
        )

    elif role == "hero":
        variants.extend(
            [
                f"{query} premium editorial photography",
                f"{query} clean professional photography",
            ]
        )

    else:
        variants.extend(
            [
                f"{query} clean professional photography",
                f"{query} studio photography",
            ]
        )

    # Remove duplicate queries while preserving order.
    unique = []

    for item in variants:
        item = _safe_text(item)

        if item and item.lower() not in {
            existing.lower() for existing in unique
        }:
            unique.append(item)

    return unique


# ---------------------------------------------------------------------------
# Unsplash API
# ---------------------------------------------------------------------------

def _search_unsplash(
    query: str,
    orientation: str = "landscape",
    per_page: int = 10,
) -> list[dict]:
    """
    Search Unsplash once.

    We use:
        - relevant ordering
        - high content safety
        - requested orientation
    """

    orientation = _normalise_orientation(
        orientation
    )

    params = (
        f"?query={quote_plus(query)}"
        f"&page=1"
        f"&per_page={max(1, min(per_page, 10))}"
        f"&order_by=relevant"
        f"&content_filter=high"
        f"&orientation={quote_plus(orientation)}"
    )

    request = Request(
        UNSPLASH_API_URL + params,
        headers={
            "Authorization": f"Client-ID {_get_access_key()}",
            "Accept-Version": "v1",
            "User-Agent": "BusinessWebsiteGenerator/1.0",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=UNSPLASH_TIMEOUT_SECONDS,
        ) as response:

            payload = json.loads(
                response.read().decode("utf-8")
            )

    except HTTPError as error:

        detail = ""

        try:
            detail = error.read().decode("utf-8")[:700]
        except Exception:
            pass

        raise RuntimeError(
            f"Unsplash API request failed ({error.code}). "
            f"{detail}"
        ) from error

    except URLError as error:

        raise RuntimeError(
            f"Could not reach Unsplash API: {error.reason}"
        ) from error

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Unsplash returned invalid JSON."
        ) from error

    results = payload.get("results", [])

    if not isinstance(results, list):
        return []

    return results


# ---------------------------------------------------------------------------
# Result quality scoring
# ---------------------------------------------------------------------------

def _score_photo(
    photo: dict,
    original_query: str,
    visual_role: str,
) -> int:
    """
    Score a photo for website suitability.

    This is intentionally conservative. Unsplash does not expose a reliable
    "transparent background" flag, so we score metadata and dimensions rather
    than pretending we can detect transparency.

    Higher score = more suitable for a professional object/product/detail use.
    """

    score = 0

    query_words = {
        word.lower()
        for word in _safe_text(original_query).split()
        if len(word) >= 3
    }

    description = _safe_text(
        photo.get("alt_description")
        or photo.get("description")
    ).lower()

    combined = description

    # Reward semantic relevance.
    matched_words = sum(
        1
        for word in query_words
        if word in combined
    )

    score += min(
        matched_words * 12,
        48,
    )

    # Strong signals for clean product/object photography.
    positive_terms = {
        "studio": 15,
        "product": 18,
        "isolated": 20,
        "white background": 22,
        "clean background": 18,
        "minimal": 10,
        "still life": 14,
        "close up": 10,
        "detail": 10,
        "object": 8,
        "equipment": 8,
        "tool": 8,
    }

    for term, points in positive_terms.items():
        if term in combined:
            score += points

    # Penalize terms that usually indicate a generic people/scene photo
    # when we explicitly asked for an object/product/detail.
    role = _safe_text(visual_role).lower()

    if role in {
        "object",
        "product",
        "instrument",
        "equipment",
        "tool",
        "ingredient",
        "material",
        "detail",
        "supporting",
    }:
        negative_terms = {
            "selfie": 30,
            "portrait": 20,
            "crowd": 18,
            "group of people": 18,
            "people": 8,
            "landscape": 10,
            "cityscape": 10,
            "building exterior": 10,
        }

        for term, points in negative_terms.items():
            if term in combined:
                score -= points

    # Prefer high-resolution images.
    width = int(photo.get("width") or 0)
    height = int(photo.get("height") or 0)

    if width >= 2500 and height >= 1500:
        score += 8
    elif width >= 1500 and height >= 1000:
        score += 4

    # Avoid extreme/awkward aspect ratios for general website composition.
    if width and height:
        ratio = width / height

        if 0.65 <= ratio <= 2.2:
            score += 5

    return score


# ---------------------------------------------------------------------------
# Convert Unsplash result into our internal asset format
# ---------------------------------------------------------------------------

def _normalise_photo(
    photo: dict,
    query: str,
    purpose: str,
    visual_role: str,
) -> dict | None:
    """Convert an Unsplash photo object to the website-builder asset format."""

    if not isinstance(photo, dict):
        return None

    urls = photo.get("urls") or {}
    links = photo.get("links") or {}
    user = photo.get("user") or {}
    user_links = user.get("links") or {}

    # IMPORTANT:
    # Use the URL returned by Unsplash. Do not construct a fake image URL.
    image_url = _safe_text(
        urls.get("regular")
        or urls.get("small")
        or urls.get("full")
    )

    source_url = _safe_text(
        links.get("html")
    )

    provider_image_id = _safe_text(
        photo.get("id")
    )

    if not image_url or not source_url or not provider_image_id:
        return None

    return {
        "provider": "unsplash",

        "provider_image_id": provider_image_id,

        "image_url": image_url,

        "source_url": _add_attribution_parameters(
            source_url
        ),

        "photographer": _safe_text(
            user.get("name")
        ),

        "photographer_url": _add_attribution_parameters(
            user_links.get("html")
        ),

        "description": _safe_text(
            photo.get("alt_description")
            or photo.get("description")
            or query
        ),

        "width": int(
            photo.get("width") or 0
        ),

        "height": int(
            photo.get("height") or 0
        ),

        "query": query,

        "purpose": (
            purpose
            if purpose in {
                "hero",
                "section",
                "supporting",
            }
            else "section"
        ),

        "visual_role": visual_role or "supporting",

        "download_location": _safe_text(
            links.get("download_location")
        ),
    }


# ---------------------------------------------------------------------------
# Main website-image search
# ---------------------------------------------------------------------------

def search_website_images(
    image_queries: list[dict],
    max_images: int = 5,
) -> list[dict]:
    """
    Search Unsplash using the AI-generated customer-showcase visual plan.

    For every requested visual:
        1. Try the original search.
        2. Try clean/studio/product variants if needed.
        3. Score returned photos.
        4. Select the strongest unique result.
        5. Return only provider-supplied image URLs.

    The result is intentionally a small curated set for facilities, products,
    menu/service details, and customer-facing visual context rather than a stock-photo gallery.
    """

    if not image_queries:
        return []

    selected = []
    used_provider_ids = set()

    for item in image_queries[:max_images]:

        if not isinstance(item, dict):
            continue

        original_query = _safe_text(
            item.get("query")
        )

        if not original_query:
            continue

        purpose = _safe_text(
            item.get("purpose")
        ).lower()

        if purpose not in {
            "hero",
            "section",
            "supporting",
        }:
            purpose = "section"

        visual_role = _safe_text(
            item.get("visual_role")
            or item.get("image_type")
            or purpose
        )

        orientation = _normalise_orientation(
            item.get("orientation")
        )

        search_queries = _build_visual_search_queries(
            original_query,
            visual_role,
        )

        candidates = []

        # Each image plan normally needs only one successful search.
        # We use fallback variants when the first result set is weak.
        for search_query in search_queries:

            results = _search_unsplash(
                query=search_query,
                orientation=orientation,
                per_page=10,
            )

            for photo in results:

                provider_id = _safe_text(
                    photo.get("id")
                )

                if (
                    not provider_id
                    or provider_id in used_provider_ids
                ):
                    continue

                score = _score_photo(
                    photo=photo,
                    original_query=original_query,
                    visual_role=visual_role,
                )

                candidates.append(
                    (
                        score,
                        photo,
                        search_query,
                    )
                )

            # If we have a strong candidate, stop making additional
            # API requests for this visual.
            if candidates:
                best_score = max(
                    candidate[0]
                    for candidate in candidates
                )

                if best_score >= 25:
                    break

        if not candidates:
            continue

        # Highest-quality candidate first.
        candidates.sort(
            key=lambda candidate: candidate[0],
            reverse=True,
        )

        chosen = None

        for score, photo, matched_query in candidates:

            provider_id = _safe_text(
                photo.get("id")
            )

            if provider_id in used_provider_ids:
                continue

            chosen = _normalise_photo(
                photo=photo,
                query=original_query,
                purpose=purpose,
                visual_role=visual_role,
            )

            if chosen:
                chosen["matched_search_query"] = (
                    matched_query
                )
                chosen["selection_score"] = score
                break

        if not chosen:
            continue

        provider_id = chosen[
            "provider_image_id"
        ]

        used_provider_ids.add(
            provider_id
        )

        selected.append(
            chosen
        )

    return selected
