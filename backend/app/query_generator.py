import json



from app.ai_management import generate_ai_text


# =========================================================
# SYSTEM PROMPT
# =========================================================

QUERY_GENERATION_PROMPT = """
Create a customer feedback questionnaire for a business.

Generate exactly {question_count} questions.

For each question, decide yourself how many answer options are appropriate.
Use between 4 and 8 options per question.

Do NOT make every question have the same number of options.
Choose the number of options based on what makes sense for that specific question.

For example:
- Some questions may need 4 options.
- Some questions may need 5 options.
- Some questions may need 6 options.
- Some questions may need 7 or 8 options when appropriate.

The questions should help collect useful information that can
later be used to create a natural customer review.

Questions and options must be specific to the business.

Do not use generic questions when the business information
allows something more relevant.

Keep questions simple enough for customers to answer quickly.

Options should be positive, realistic, distinct from each other,
and easy for a customer to select.

Do not invent specific services, people, prices, guarantees,
results, or facts that are not present in the business information.

Return ONLY valid JSON in this exact structure:

{{
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option 1",
        "Option 2",
        "Option 3",
        "Option n"
      ]
    }}
  ]
}}
"""


# =========================================================
# GENERATE QUESTIONS
# =========================================================

def generate_questions(
    business_name: str,
    business_type: str,
    about_business: str,
    year_established: int,
    question_count: int = 4,
) -> list[dict]:

    prompt = QUERY_GENERATION_PROMPT.format(question_count=question_count)

    user_input = f"""
        Business Name:
        {business_name}

        Business Type:
        {business_type}

        About Business:
        {about_business}

        Year Established:
        {year_established}

        Create the customer questionnaire for this business.
        """

    try:

        raw_output = generate_ai_text(
            user_input,
            system_instruction=prompt,
            temperature=0.9,
            max_output_tokens=1500,
        )

    except Exception as error:

        print(f"Gemini question generation error: {error}")

        raise RuntimeError(
            f"Gemini API request failed: {error}"
        ) from error

    if not raw_output:
        raise RuntimeError(
            "AI returned an empty questionnaire."
        )

    # -----------------------------------------------------
    # Remove accidental markdown JSON fences
    # -----------------------------------------------------

    if raw_output.startswith("```json"):
        raw_output = raw_output[7:]

    elif raw_output.startswith("```"):
        raw_output = raw_output[3:]

    if raw_output.endswith("```"):
        raw_output = raw_output[:-3]

    raw_output = raw_output.strip()

    # -----------------------------------------------------
    # Parse JSON
    # -----------------------------------------------------

    try:

        data = json.loads(raw_output)

    except json.JSONDecodeError as error:

        print("Invalid Gemini JSON:")
        print(raw_output)

        raise RuntimeError(
            "AI returned invalid questionnaire data."
        ) from error

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise RuntimeError(
            "AI response does not contain questions."
        )

    # -----------------------------------------------------
    # Validate exactly 4 questions
    # -----------------------------------------------------

    if len(questions) != question_count:
        raise RuntimeError(
            f"AI must generate exactly "
            f"{question_count} questions."
        )

    validated_questions = []

    for question in questions:

        if not isinstance(question, dict):
            raise RuntimeError(
                "Invalid question format."
            )

        question_text = str(
            question.get("question", "")
        ).strip()

        options = question.get("options")

        if not question_text:
            raise RuntimeError(
                "A generated question is empty."
            )

        if not isinstance(options, list):
            raise RuntimeError(
                "Question options are invalid."
            )

        options = [
            str(option).strip()
            for option in options
            if str(option).strip()
        ]

        if len(options) < 4:
            raise RuntimeError(
                "Each question must have at least 4 options."
            )

        if len(options) > 8:
            options = options[:8]

        validated_questions.append(
            {
                "question": question_text,
                "options": options,
            }
        )

    return validated_questions