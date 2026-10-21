import json
import re

from app.ai_management import generate_ai_text


def _extract_json(text: str) -> dict:
    cleaned = (text or "").strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end <= start:
            raise RuntimeError(
                "AI returned invalid JSON."
            )

        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "AI returned invalid JSON."
            ) from error

    if not isinstance(data, dict):
        raise RuntimeError(
            "AI returned JSON, but not a JSON object."
        )

    return data


def _generate_text(
    prompt: str,
    temperature: float = 0.7,
    max_output_tokens: int = 12000,
) -> str:
    """Generate website content through the centralized AI provider layer."""
    return generate_ai_text(
        prompt=prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


def _generate_json(
    prompt: str,
    temperature: float = 0.8,
    max_output_tokens: int = 3000,
) -> dict:
    return _extract_json(
        _generate_text(
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    )


WEBSITE_QUESTION_PROMPT = """
You are an expert customer-facing business showcase information architect.

Create a business-specific questionnaire for a single-page customer showcase.
The purpose is NOT to collect information for a conventional corporate website.
The purpose is to help a business owner clearly present what customers can
actually see, use, buy, book, choose, or compare.

The questionnaire MUST change substantially according to the business type.
Focus on practical customer-facing information such as facilities,
amenities, services, treatments, products, menu/catalog items, packages,
rate lists, pricing, options, policies, and useful visit information.

BUSINESS-SPECIFIC DIRECTION

RESTAURANT / CAFE / FOOD BUSINESS:
- menu categories and important items
- signature dishes or specialties
- prices/rate list when available
- serving sizes, variants, combos, or packages when relevant
- dietary options when actually offered
- dine-in, takeaway, or delivery facilities when supplied
- opening hours and location/contact only if not already known

DENTAL / MEDICAL / CLINIC:
- treatments/services offered
- treatment-specific facilities and equipment
- specialties or areas of care
- consultation/appointment information
- treatment packages or published fees/rates when available
- patient facilities and useful visit information
- emergency/urgent-care availability only if actually offered

SALON / SPA / BEAUTY:
- services and service categories
- packages
- rate list/prices
- facilities and treatment areas
- products or brands only if supplied
- booking and visit information

GYM / FITNESS:
- facilities and equipment
- memberships and pricing
- programs/classes
- personal training or other services
- amenities and timings

HOTEL / RESORT:
- room categories and rates when available
- amenities/facilities
- dining options/menu information
- experiences and activities
- packages
- check-in/policy information when supplied

RETAIL / CLOTHING / FASHION:
- product categories
- collections or product ranges
- prices/rate ranges when available
- sizes, variants, materials, or customization when supplied
- store facilities and shopping options

SERVICE BUSINESS / OTHER:
Identify the most useful customer-facing information for THAT business.
Prioritize what customers need to understand the offering and make a visit,
purchase, booking, or enquiry decision.

RULES:
- Ask 8 to 12 questions.
- Do not ask for information already present in business_info.
- Do not ask technical questions.
- Do not ask for passwords, API keys, or website-development details.
- Do not invent prices, services, facilities, products, staff, claims, or policies.
- Ask the owner to provide prices/rates only if their business normally publishes them.
- Questions must be easy for a business owner to answer.
- Prefer questions that produce concrete customer-facing content over vague marketing copy.
- Ask for a complete list when a list is important, e.g. menu items, services,
  facilities, amenities, packages, or rates.
- If exact prices are not available, allow the owner to say that pricing is
  enquiry-based or not published; do not force invented prices.
- Do not repeat information already supplied in the business description.
- Return only valid JSON.

Return:
{
  "questions": [
    {
      "question_key": "snake_case",
      "question_text": "Question",
      "input_type": "textarea",
      "required": true,
      "placeholder": "Example",
      "helper_text": "Short help"
    }
  ]
}
"""


def generate_website_questions(business: dict) -> list[dict]:
    prompt = f"""
{WEBSITE_QUESTION_PROMPT}

BUSINESS:
Name: {business.get("business_name", "")}
Type: {business.get("business_type", "")}
About: {business.get("about_business", "")}
Established: {business.get("year_established", "")}

Create the questionnaire specifically for this business.
"""

    data = _generate_json(
        prompt,
        temperature=0.9,
        max_output_tokens=3000,
    )

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise RuntimeError(
            "AI did not return website questions."
        )

    normalized = []

    for index, item in enumerate(
        questions[:12],
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        text = str(
            item.get("question_text", "")
        ).strip()

        if not text:
            continue

        key = str(
            item.get(
                "question_key",
                f"question_{index}",
            )
        ).strip() or f"question_{index}"

        normalized.append(
            {
                "question_order": index,
                "question_key": key[:100],
                "question_text": text[:1000],
                "input_type": "textarea",
                "required": bool(
                    item.get("required", True)
                ),
                "placeholder": str(
                    item.get("placeholder", "")
                ).strip()[:500],
                "helper_text": str(
                    item.get("helper_text", "")
                ).strip()[:500],
            }
        )

    if len(normalized) < 5:
        raise RuntimeError(
            "AI generated too few useful website questions."
        )

    return normalized


def _format_answers(answers: list[dict]) -> str:
    parts = []

    for index, item in enumerate(
        answers,
        start=1,
    ):
        question = str(
            item.get("question", "")
        ).strip()

        answer = str(
            item.get("answer", "")
        ).strip()

        if not question or not answer:
            continue

        parts.append(
            f"QUESTION {index}:\n"
            f"{question}\n\n"
            f"OWNER ANSWER:\n"
            f"{answer}"
        )

    return "\n\n".join(parts)



WEBSITE_IMAGE_QUERY_PROMPT = """
You are an expert commercial visual art director creating imagery for a
customer-facing business facility, services, menu, and rate-card showcase.

The goal is NOT to make a generic corporate website or fill a page with stock
photography. Select real photographic subjects that help customers understand
what the business offers and what they can expect to see, use, buy, eat, book,
or experience.

VISUAL PRIORITIES

1. FACILITIES / AMENITIES:
Search for relevant equipment, rooms, counters, treatment areas, seating,
machines, tools, fixtures, amenities, or other physical facilities when
supported by the business information.

2. PRODUCTS / MENU / CATALOG:
For restaurants, food businesses, retail, salons, clinics, and similar
businesses, prioritize relevant products, dishes, ingredients, tools,
materials, or service details. Never invent a specific branded item.

3. SERVICES / TREATMENTS:
Use visual details of the actual service environment, instruments, equipment,
materials, or treatment setup when supported. Prefer concrete detail shots over
generic smiling-person stock photos.

4. RATE / PACKAGE PRESENTATION:
Do not search for generic money, price-tag, or currency stock photos. Pricing
should be represented through clean typography, tables, cards, or badges in
HTML. Images should support the actual offering instead.

5. HERO / ENVIRONMENT:
Use one broader environment image only when it materially helps customers
understand the business. Do not default to a generic building exterior.

CATEGORY EXAMPLES

DENTAL / MEDICAL:
dental chair, treatment room detail, dental instruments, relevant equipment,
sterile clinical setup, treatment detail.

RESTAURANT / CAFE:
signature-style food, menu-relevant dish category, ingredients, tableware,
serving details, coffee/food preparation details.

SALON / SPA:
professional tools, treatment setup, styling equipment, clean salon detail,
beauty products when supplied.

GYM:
strength equipment, cardio machines, training accessories, facility details.

HOTEL / RESORT:
room details, amenities, dining setup, bathroom details, hospitality spaces.

RETAIL / FASHION:
product details, fabrics, accessories, display details, relevant merchandise.

OTHER BUSINESSES:
Identify the most recognizable physical objects, products, tools, materials,
equipment, facilities, or visual details associated with the supplied business.

IMAGE STRATEGY
- Return 3 to 5 image queries.
- Use different visual roles rather than five similar photos.
- Prefer 2 to 4 facility/product/detail images and at most 1 broader environment image.
- Do not invent a specific product, dish, treatment, facility, or brand unsupported by the supplied information.
- Generic category-level visuals are allowed when they are inherent to the business.
- Choose orientation deliberately: landscape for hero/environment, portrait for
  product/detail compositions, square for compact showcase cards.
- The purpose must be hero, section, or supporting.
- Queries must be concrete enough for Unsplash search.

Return ONLY valid JSON:
{
  "image_queries": [
    {
      "query": "specific search query",
      "purpose": "hero",
      "orientation": "landscape",
      "visual_role": "short description"
    }
  ]
}
"""


def generate_website_image_queries(
    business: dict,
    answers: list[dict],
) -> list[dict]:
    """
    Generate a business-specific visual plan before searching Unsplash.
    """

    answers_text = _format_answers(answers)

    prompt = f"""
{WEBSITE_IMAGE_QUERY_PROMPT}

BUSINESS INFORMATION

Business name:
{business.get("business_name", "")}

Business type:
{business.get("business_type", "")}

About business:
{business.get("about_business", "")}

Year established:
{business.get("year_established", "")}

OWNER-PROVIDED WEBSITE INFORMATION

{answers_text}

Now create the visual image-search plan.

Think like a professional commercial art director:
choose images that can become part of the composition, not a gallery of
generic stock photos.

Prioritize real physical details, products, tools, instruments, materials,
ingredients, equipment, and other recognizable visual elements of this
business.

Return only the JSON object.
"""

    data = _generate_json(
        prompt,
        temperature=0.85,
        max_output_tokens=2500,
    )

    queries = data.get("image_queries")

    if not isinstance(queries, list):
        raise RuntimeError(
            "AI did not return website image queries."
        )

    normalized = []

    for item in queries[:5]:
        if not isinstance(item, dict):
            continue

        query = str(
            item.get("query", "")
        ).strip()

        if not query:
            continue

        purpose = str(
            item.get("purpose", "section")
        ).strip().lower()

        if purpose not in {
            "hero",
            "section",
            "supporting",
        }:
            purpose = "section"

        orientation = str(
            item.get("orientation", "landscape")
        ).strip().lower()

        if orientation not in {
            "landscape",
            "portrait",
            "square",
        }:
            orientation = "landscape"

        visual_role = str(
            item.get("visual_role", "")
        ).strip()

        normalized.append(
            {
                "query": query[:500],
                "purpose": purpose,
                "orientation": orientation,
                "visual_role": visual_role[:300],
            }
        )

    if len(normalized) < 2:
        raise RuntimeError(
            "AI generated too few useful website image queries."
        )

    return normalized


def _format_image_assets(
    image_assets: list[dict] | None,
) -> str:
    """
    Format backend-selected Unsplash assets for the HTML-generation prompt.
    """

    if not image_assets:
        return "No real image assets were found. Use CSS/SVG artwork instead."

    lines = []

    for index, asset in enumerate(
        image_assets,
        start=1,
    ):
        lines.append(
            f"""
IMAGE ASSET {index}
Provider: {asset.get("provider", "unsplash")}
Image URL: {asset.get("image_url", "")}
Source URL: {asset.get("source_url", "")}
Photographer: {asset.get("photographer", "")}
Photographer URL: {asset.get("photographer_url", "")}
Search query: {asset.get("query", "")}
Purpose: {asset.get("purpose", "section")}
Visual role: {asset.get("visual_role", "")}
Width: {asset.get("width", 0)}
Height: {asset.get("height", 0)}
""".strip()
        )

    return "\n\n".join(lines)



def _clean_generated_html(html: str) -> str:
    cleaned = (html or "").strip()

    cleaned = re.sub(
        r"^```(?:html)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    start = cleaned.lower().find("<!doctype")
    if start == -1:
        start = cleaned.lower().find("<html")

    if start > 0:
        cleaned = cleaned[start:]

    return cleaned.strip()

def _validate_in_page_links(html: str) -> None:
    """Reject only genuinely broken in-page anchor links."""
    ids = {
        value
        for value in re.findall(
            r'\bid\s*=\s*["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
    }

    for target in re.findall(
        r'\bhref\s*=\s*["\']#([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    ):
        if target and target not in ids:
            raise RuntimeError(
                f"AI generated an in-page link to missing section '#{target}'."
            )


def _validate_html(html: str) -> str:
    cleaned = _clean_generated_html(html)

    if len(cleaned) < 1000:
        raise RuntimeError(
            "AI generated website code is too short."
        )

    lower = cleaned.lower()

    if "<html" not in lower:
        raise RuntimeError(
            "AI did not generate a complete HTML document."
        )

    if "<style" not in lower:
        raise RuntimeError(
            "AI website does not contain CSS."
        )

    if "<meta" not in lower or "viewport" not in lower:
        raise RuntimeError(
            "AI website is missing the mobile viewport."
        )

    # The site is rendered inside a sandboxed iframe.
    # Do not allow dangerous document-level embedding behavior.
    cleaned = re.sub(
        r"<base\b[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Never allow generated navigation code to replace the iframe document.
    forbidden_navigation = re.search(
        r"(?:window\.location|location\.(?:href|assign|replace)|document\.write|<meta[^>]+http-equiv\s*=\s*[\"']?refresh)",
        cleaned,
        flags=re.IGNORECASE,
    )

    if forbidden_navigation:
        raise RuntimeError(
            "AI generated unsafe document-navigation code. Please regenerate the website."
        )

    # Reject relative document-navigation links that can replace the iframe
    # page when a customer taps a menu item. Safe navigation is limited to
    # in-page anchors, explicit contact links, and explicitly supplied URLs.
    unsafe_href = re.search(
        r"href\s*=\s*[\"'](?:/|\./|\.\./|index\.html(?:[?#]|\"|'))",
        cleaned,
        flags=re.IGNORECASE,
    )

    if unsafe_href:
        raise RuntimeError(
            "AI generated a relative page-navigation link. Please regenerate the website."
        )

    # Reject common placeholder / invented image sources.
    placeholder_image = re.search(
        r'<img\b[^>]+src\s*=\s*["\'](?:https?://)?(?:'
        r'placehold\.co|placehold\.it|placeholder\.com|'
        r'via\.placeholder\.com|dummyimage\.com)',
        cleaned,
        flags=re.IGNORECASE,
    )

    if placeholder_image:
        raise RuntimeError(
            "AI generated a placeholder image source."
        )

    # Generated websites may only use image URLs that were supplied by the
    # backend when image assets are available. The stricter exact-URL check
    # is performed in generate_website_html().

    # Defensive interaction layer. It does not impose a visual template.
    interaction_script = """<script>
(function () {
  "use strict";

  function closeMenus(except) {
    document.querySelectorAll('[aria-expanded="true"]').forEach(function (button) {
      if (except && button === except) return;
      button.setAttribute("aria-expanded", "false");
      var controlledId = button.getAttribute("aria-controls");
      if (!controlledId) return;
      var panel = document.getElementById(controlledId);
      if (panel) {
        panel.hidden = true;
        panel.classList.remove("is-open", "open", "active");
      }
    });
  }

  document.querySelectorAll("[aria-controls]").forEach(function (button) {
    var controlledId = button.getAttribute("aria-controls");
    var panel = document.getElementById(controlledId);
    if (!panel) return;

    var isExpanded = button.getAttribute("aria-expanded") === "true";
    panel.hidden = !isExpanded;

    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var open = button.getAttribute("aria-expanded") === "true";
      closeMenus(button);
      button.setAttribute("aria-expanded", String(!open));
      panel.hidden = open;
      panel.classList.toggle("is-open", !open);
      panel.classList.toggle("open", !open);
      panel.classList.toggle("active", !open);
    });
  });

  document.querySelectorAll("[data-dropdown-toggle]").forEach(function (button) {
    var targetId = button.getAttribute("data-dropdown-toggle");
    var panel = document.getElementById(targetId);
    if (!panel) return;

    button.setAttribute("aria-expanded", button.getAttribute("aria-expanded") === "true" ? "true" : "false");
    panel.hidden = button.getAttribute("aria-expanded") !== "true";

    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var open = button.getAttribute("aria-expanded") === "true";
      closeMenus(button);
      button.setAttribute("aria-expanded", String(!open));
      panel.hidden = open;
      panel.classList.toggle("is-open", !open);
      panel.classList.toggle("open", !open);
      panel.classList.toggle("active", !open);
    });
  });

  document.addEventListener("click", function (event) {
    if (!event.target.closest("[aria-controls], [data-dropdown-toggle]")) {
      closeMenus();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeMenus();
  });

  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener("click", function (event) {
      var href = link.getAttribute("href");
      if (!href || href === "#") return;
      var target = document.querySelector(href);
      if (!target) return;
      event.preventDefault();
      closeMenus();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  document.querySelectorAll("[aria-controls], [data-dropdown-toggle]").forEach(function (button) {
    button.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        button.click();
      }
    });
  });
})();
</script>"""

    if re.search(r"</body>\s*</html>\s*$", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(
            r"</body>",
            interaction_script + "\n</body>",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        cleaned += "\n" + interaction_script

    return cleaned


WEBSITE_HTML_PROMPT = """
You are a senior award-winning web designer, visual art director,
commercial showcase designer, UX designer, and front-end engineer.

Create ONE complete, production-quality, customer-facing business showcase
as a SINGLE self-contained HTML document.

IMPORTANT PRODUCT DEFINITION

This is NOT a conventional company website, corporate website, portfolio,
landing page, or generic business website.

It is a practical CUSTOMER SHOWCASE: a digital display/menu/catalog that lets
a business owner present what customers can see, use, buy, eat, book, choose,
or compare.

The primary content should therefore be drawn from the supplied owner answers
and organized around the business's real offerings.

CORE SHOWCASE CONTENT

Depending on the business, naturally prioritize the sections that are actually
supported by the supplied information:

- Facilities / Amenities
- Services / Treatments
- Menu / Product Catalog
- Rate List / Pricing
- Packages / Plans
- Products / Specialties
- What's Included / Options
- Visit / Booking Information
- Location / Contact

Do NOT force every section into every business. If a business does not have a
menu, do not create a fake menu. If prices are not supplied, do not invent them.
If facilities are not supplied, do not invent facilities. Build around what is
actually available.

The page should feel like a premium digital brochure, menu, facility board,
service catalog, or rate-card experience rather than a marketing-heavy website.

BUSINESS-SPECIFIC FEEL

A restaurant should feel like an elegant digital menu and dining showcase.
A dental clinic should feel like a clean treatment/facility/service showcase.
A salon should feel like a service + facility + rate-card showcase.
A gym should feel like a facilities + membership + program showcase.
A hotel should feel like an amenities + rooms + experiences + rates showcase.
A retail store should feel like a product catalog/showroom.
Other businesses should receive the most natural customer-showcase format.

==================================================
CUSTOMER EXPERIENCE
==================================================

A customer should be able to understand within seconds:
1. What this business offers.
2. What facilities, products, services, menu items, or packages are available.
3. What options or rates are available when supplied.
4. How the offerings are organized.
5. How to contact, visit, or enquire when that information is supplied.

Use clear labels, short descriptions, visual grouping, and scannable pricing.
Avoid long marketing paragraphs.

==================================================
MOBILE FIRST
==================================================

MOBILE FIRST IS MANDATORY.

Design for 360px to 430px first:
- thumb-friendly controls
- large readable typography
- no horizontal scrolling
- compact but comfortable cards
- sticky/mobile navigation when appropriate
- vertically scannable menu/rate lists
- touch-friendly interactions
- responsive desktop/tablet enhancement

==================================================
SHOWCASE DESIGN SYSTEM
==================================================

Choose a composition appropriate to the business. Do not mechanically reuse a
fixed template.

Possible visual patterns include, where appropriate:
- menu-style categorized lists
- elegant rate tables
- facility tiles
- service cards
- product cards
- package comparison blocks
- icon-led amenity lists
- editorial image + information layouts
- compact specification rows
- category tabs or accordions
- visual feature strips
- sticky section navigation

Pricing and rate information must be especially easy to scan. When prices are
provided, show the exact supplied values clearly and consistently. Never alter
or embellish owner-provided prices.

Use tasteful CSS/SVG icons for facilities, categories, and small visual cues.
Do not depend on icon libraries or external scripts.

==================================================
VISUAL QUALITY
==================================================

The result must look like a professional commercial digital showcase:
- premium
- modern
- distinctive
- clean
- highly scannable
- strong hierarchy
- refined spacing
- category-appropriate typography
- intentional image placement
- restrained decoration
- subtle motion where useful

Avoid:
- generic SaaS dashboard styling
- corporate-template appearance
- huge marketing hero sections that push useful information below the fold
- excessive gradients
- childish UI
- repetitive card grids
- fake testimonials/reviews
- fake statistics
- unnecessary decorative noise
- giant paragraphs

The useful customer information should remain visually dominant.

==================================================
IMAGES
==================================================

Use ONLY the real image assets supplied by the backend.

Do NOT:
- invent image URLs
- search the web from JavaScript
- call Unsplash from the generated website
- use another image provider
- use random remote images
- use placeholder.com
- use broken image URLs
- use data URLs for external images
- use base64 image data

When images are supplied, choose them according to their stated purpose and
visual role. Use at least 2 different supplied images when the content supports
it, but do not turn the showcase into a gallery.

Prefer images that explain the business: facilities, products, dishes,
equipment, tools, materials, treatment environments, or other real details.

If an image is not useful for a particular section, use CSS/SVG instead.

Unsplash attribution metadata supplied by the backend should be included in a
small tasteful footer/credit area without distracting from the showcase.

==================================================
FACTUAL ACCURACY — ABSOLUTE RULE
==================================================

Use ONLY:
1. supplied business_info
2. supplied owner answers
3. supplied image metadata for image credits

NEVER invent:
- prices or rates
- menu items
- products
- services
- treatments
- facilities
- amenities
- doctors/staff
- opening hours
- address
- phone/email
- ratings/reviews
- awards
- guarantees
- statistics
- discounts
- package contents
- policies

If information is missing, simply do not show that information.
Do not create fake content to fill space.
Do not repeat the same information across multiple sections.

==================================================
FUNCTIONALITY
==================================================

FUNCTIONALITY IS MANDATORY:
- Every visible button must have a real purpose.
- Navigation must stay inside the generated document.
- Use safe in-page anchors such as #facilities, #services, #menu, #rates,
  #contact only when those sections exist.
- Never use href="/", href="./", href="index.html", or other document-changing links.
- Never use window.location, location.href, location.assign, location.replace,
  document.write, meta refresh, or redirects.
- Mobile menu buttons must only open/close the menu.
- Accordions/dropdowns must expand/collapse correctly and close on Escape or
  outside click where appropriate.
- Internal anchor links should smoothly scroll without replacing the document.
- Contact buttons may use tel: or mailto: ONLY when explicitly supplied.
- External URLs may be used only when explicitly supplied by the owner and must
  open safely in a new tab.
- All controls need accessible labels and correct ARIA state.
- The showcase must remain usable without JavaScript.
- Use only small self-contained vanilla JavaScript when interaction is genuinely needed.
- No backend calls.
- No API calls.
- No fake submission forms.
- No external scripts.
- No React.
- No Tailwind.
- No Bootstrap.
- No JavaScript frameworks.

==================================================
TECHNICAL OUTPUT
==================================================

Return ONLY the complete HTML document.
No markdown fences.
No explanation before or after it.

The document MUST contain:
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>...</style>
</head>
<body>...</body>
</html>

Use semantic HTML and accessible labels.

==================================================
FINAL DESIGN DECISION
==================================================

You are responsible for choosing the right:
- showcase format
- section hierarchy
- menu/rate-list presentation
- typography
- colors
- image placement and crop
- card/list treatment
- navigation
- decorative treatment
- interaction pattern

Do NOT mechanically follow a fixed template.
Build this as a custom customer-facing showcase for this exact business.
"""



def generate_website_html(
    business: dict,
    answers: list[dict],
    image_assets: list[dict] | None = None,
    color_theme_1: str | None = None,
    color_theme_2: str | None = None,
) -> str:
    """
    Generate the final website HTML using business information,
    owner answers, and backend-selected real image assets.
    """

    answers_text = _format_answers(answers)

    if not answers_text:
        raise RuntimeError(
            "No valid website answers were provided."
        )

    image_assets_text = _format_image_assets(
        image_assets
    )

    color_1 = str(color_theme_1 or "").strip() or "AI CHOICE"
    color_2 = str(color_theme_2 or "").strip() or "AI CHOICE"

    if color_1 == "AI CHOICE" and color_2 == "AI CHOICE":
        color_direction = (
            "No colors were selected by the owner. Choose both primary and "
            "secondary brand colors yourself based on the business category."
        )
    elif color_1 == "AI CHOICE":
        color_direction = (
            f"Owner selected secondary/theme color: {color_2}. Choose a "
            "compatible primary color that creates a polished, accessible palette."
        )
    elif color_2 == "AI CHOICE":
        color_direction = (
            f"Owner selected primary/theme color: {color_1}. Choose a "
            "compatible secondary color that creates a polished, accessible palette."
        )
    else:
        color_direction = (
            f"Owner explicitly selected the two theme colors: {color_1} and {color_2}. "
            "Use these exact colors as the core brand palette. Do not replace them "
            "with different colors."
        )

    prompt = f"""
{WEBSITE_HTML_PROMPT}

COLOR THEME DIRECTION

{color_direction}


BUSINESS INFORMATION

Business name:
{business.get("business_name", "")}

Business type:
{business.get("business_type", "")}

About business:
{business.get("about_business", "")}

Year established:
{business.get("year_established", "")}


OWNER-PROVIDED WEBSITE INFORMATION

{answers_text}


REAL IMAGE ASSETS SELECTED BY THE BACKEND

{image_assets_text}


Now design the complete website.

Make the design strongly specific to this business category.

Use the supplied real images as intentional visual design elements.

Do NOT simply put one large stock photo at the top.

Think creatively about how the physical objects, products, tools,
instruments, ingredients, materials, or equipment represented by the supplied
images can become part of the visual identity.

Choose the right image, right size, right crop, right placement, and right UI
composition for each section.

Prioritize mobile presentation first.

Return ONLY the complete HTML document.
"""

    html = _generate_text(
        prompt,
        temperature=1.0,
        max_output_tokens=16000,
    )

    cleaned = _clean_generated_html(html)

    # If image assets were supplied, require the generated HTML to actually
    # use at least one exact backend-provided image URL.
    if image_assets:
        allowed_urls = {
            str(asset.get("image_url", "")).strip()
            for asset in image_assets
            if str(asset.get("image_url", "")).strip()
        }

        if allowed_urls:
            used_image = any(
                url in cleaned
                for url in allowed_urls
            )

            if not used_image:
                raise RuntimeError(
                    "AI generated website did not use the supplied real image assets."
                )

    cleaned = _validate_html(cleaned)
    _validate_in_page_links(cleaned)

    # Keep owner-selected colors embedded in the final document so the
    # generated website has a durable record of the requested brand palette.
    # The AI remains responsible for the actual art direction and composition.
    selected_colors = [color for color in (color_theme_1, color_theme_2) if color]
    if selected_colors:
        missing_colors = [
            color for color in selected_colors
            if color.lower() not in cleaned.lower()
        ]
        if missing_colors:
            theme_metadata = (
                '<style id="owner-color-theme">:root{'
                + ';'.join(
                    f'--owner-theme-{index + 1}:{color}'
                    for index, color in enumerate(selected_colors)
                )
                + '}</style>'
            )
            cleaned = re.sub(
                r"</head>",
                theme_metadata + "</head>",
                cleaned,
                count=1,
                flags=re.IGNORECASE,
            )

    return cleaned



# Backward-compatible function name.
# The new router should use generate_website_html.
def generate_website_config(
    business: dict,
    answers: list[dict],
    image_assets: list[dict] | None = None,
    color_theme_1: str | None = None,
    color_theme_2: str | None = None,
) -> dict:
    html = generate_website_html(
        business,
        answers,
        image_assets=image_assets,
        color_theme_1=color_theme_1,
        color_theme_2=color_theme_2,
    )

    return {
        "render_mode": "generated_html",
        "html": html,
    }
