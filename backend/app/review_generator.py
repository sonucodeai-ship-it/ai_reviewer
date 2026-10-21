"""
Review generation service.

This module owns the review-generation prompt and the business logic required
for converting customer questionnaire answers into a natural Google review.

AI provider/API management is intentionally delegated to:
    app.ai_management.generate_ai_text

This separation keeps the application provider-agnostic. If the project later
moves from Gemini to OpenAI or another AI provider, this module should not
require provider-specific changes.
"""

from __future__ import annotations

from typing import Any

from app.ai_management import generate_ai_text


# =========================================================
# REVIEW GENERATION PROMPT
# =========================================================

REVIEW_SYSTEM_PROMPT = """
You write genuine Google reviews from a customer's
provided experience with a business.

Turn the customer's selected answers into a natural,
personal and believable review.

The most important goal is AUTHENTICITY.

The review should sound like something a real customer
would actually write on Google.

Do not write like an AI, marketer, copywriter, SEO writer,
advertisement or professional testimonial.

Do not use a fixed template.

Do not always begin with:
"I visited",
"I recently visited",
"I had a great experience",
"My experience",
or similar openings.

Choose the most natural opening based on the information
provided.

Naturally vary:

- opening
- sentence structure
- length
- rhythm
- vocabulary
- order of details
- emotional expression
- ending

Do not force every provided answer into the review.

Use only the details that naturally fit together.

Some reviews can be short and spontaneous.
Some can be slightly more detailed.
Some can be warm and appreciative.
Some can be simple and matter-of-fact.

The language should feel like everyday Indian English.

Keep it easy to read and conversational.

Do not deliberately add grammatical mistakes
or forced Indian slang.

Use the customer's selected information as the
only source of experience.

Never invent:

- services
- products
- treatments
- results
- outcomes
- prices
- discounts
- waiting times
- staff behavior
- facilities
- conversations
- equipment
- procedures
- guarantees
- business claims
- personal experiences
- facts that were not provided

Do not exaggerate.

Do not create unsupported claims such as:

"best business"
"number one"
"100% recommended"
"world-class"
"life-changing"
or similar promotional language.

Do not add SEO keywords unnaturally.

Do not stuff keywords such as:
"best"
"top"
"near me"
or location keywords.

If a business/service/product is relevant to the
customer's selected experience, mention it naturally.

Emojis are optional.

Use at most one emoji, and only when it genuinely fits.

Do not use emojis in every review.

Do not use hashtags.

Do not use headings.

Do not use bullet points.

Do not add quotation marks around the review.

Do not explain what you wrote.

Return ONLY the finished review.
""".strip()


# =========================================================
# INTERNAL HELPERS
# =========================================================


def _clean_text(value: Any) -> str:
    """
    Safely convert a value to stripped text.

    Questionnaire data normally arrives as strings, but this helper keeps the
    generator resilient to None or unexpected values without introducing
    provider-specific logic.
    """

    if value is None:
        return ""

    return str(value).strip()


def _clean_selected_options(options: Any) -> list[str]:
    """
    Normalize selected questionnaire options into a clean list of strings.

    Invalid, empty, or whitespace-only values are ignored.
    """

    if not options:
        return []

    if isinstance(options, str):
        cleaned = _clean_text(options)
        return [cleaned] if cleaned else []

    try:
        return [
            cleaned
            for option in options
            if (cleaned := _clean_text(option))
        ]
    except TypeError:
        cleaned = _clean_text(options)
        return [cleaned] if cleaned else []


# =========================================================
# FORMAT CUSTOMER ANSWERS
# =========================================================


def format_answers(answers: list[Any]) -> str:
    """
    Convert dynamic customer questions and selected options into a clean,
    deterministic prompt section.

    Expected answer shape:
        answer.question
        answer.selected_options

    The function intentionally does not know anything about the business type
    or the AI provider. It only prepares the customer's supplied information.
    """

    formatted_sections: list[str] = []

    for index, answer in enumerate(answers, start=1):
        if answer is None:
            continue

        question = _clean_text(getattr(answer, "question", ""))
        selected_options = _clean_selected_options(
            getattr(answer, "selected_options", [])
        )

        if not question or not selected_options:
            continue

        options_text = "\n".join(
            f"  - {option}"
            for option in selected_options
        )

        formatted_sections.append(
            f"Question {index}: {question}\n"
            f"Customer selected:\n"
            f"{options_text}"
        )

    return "\n\n".join(formatted_sections)


# =========================================================
# BUILD USER PROMPT
# =========================================================


def _build_user_input(customer_answers: str) -> str:
    """
    Build the user-side generation prompt.

    The review-generation instructions remain in this feature module while
    the actual AI API call is handled centrally by app.ai_management.
    """

    return f"""
Customer's actual selections:

{customer_answers}

Write one natural Google review based only
on the customer's selected experience.

Do not invent any additional information.
""".strip()


# =========================================================
# CLEAN GENERATED REVIEW
# =========================================================


def _clean_generated_review(review: str) -> str:
    """
    Clean harmless formatting artifacts from the AI response.

    The AI management layer is responsible for provider/API handling. This
    function is responsible only for feature-level output normalization.
    """

    cleaned = _clean_text(review)

    # Some models may still return the review wrapped in quotation marks even
    # though the prompt explicitly asks them not to.
    if (
        len(cleaned) >= 2
        and cleaned.startswith('"')
        and cleaned.endswith('"')
    ):
        cleaned = cleaned[1:-1].strip()

    return cleaned


# =========================================================
# GENERATE REVIEW
# =========================================================


def generate_review(answers: list[Any]) -> str:
    """
    Generate a natural Google review from dynamic questionnaire answers.

    This function is business-agnostic and can work for clinics, restaurants,
    salons, hotels, service businesses, retail businesses, and other business
    types.

    AI provider/API management is centralized in app.ai_management.
    """

    if not answers:
        raise RuntimeError(
            "No customer answers were provided."
        )

    customer_answers = format_answers(answers)

    if not customer_answers:
        raise RuntimeError(
            "No valid customer answers were provided."
        )

    # Build the user prompt before calling the centralized AI management layer.
    # This is intentionally kept here because the review-generation content
    # belongs to this feature, not to the provider-management module.
    user_input = _build_user_input(customer_answers)

    try:
        review = generate_ai_text(
            user_input,
            system_instruction=REVIEW_SYSTEM_PROMPT,
            temperature=1.0,
            max_output_tokens=220,
        )
    except Exception as error:
        # Keep the feature-level error meaningful while preserving the
        # original exception as the cause for server-side debugging.
        print(f"Review generation error: {error}")

        raise RuntimeError(
            f"Review generation failed: {error}"
        ) from error

    review = _clean_generated_review(review)

    if not review:
        raise RuntimeError(
            "AI provider returned an empty review."
        )

    return review
