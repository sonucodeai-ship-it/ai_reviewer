from pydantic import BaseModel, Field


class WebsiteAnswerRequest(BaseModel):
    question_id: int
    answer: str = Field(default="", max_length=10000)


class WebsiteGenerateRequest(BaseModel):
    answers: list[WebsiteAnswerRequest]
    # Optional brand colors. When omitted/null, AI chooses the palette.
    color_theme_1: str | None = Field(default=None, max_length=7)
    color_theme_2: str | None = Field(default=None, max_length=7)


class WebsiteQuestionResponse(BaseModel):
    question_id: int
    question_order: int
    question_key: str
    question_text: str
    input_type: str
    required: bool
    placeholder: str | None = None
    helper_text: str | None = None
