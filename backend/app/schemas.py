from pydantic import AnyHttpUrl, BaseModel, EmailStr, Field


# =========================================================
# REVIEW SCHEMAS
# =========================================================


class ReviewAnswer(BaseModel):
    """
    Represents one question and the options selected
    by the customer on the Dashboard.
    """

    query_id: int | None = None

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    selected_options: list[str] = Field(
        ...,
        min_length=1,
    )


class ReviewRequest(BaseModel):
    """
    Generic review generation request.

    The review system is intentionally business-agnostic.
    Questions and options can belong to any type of business.
    """

    answers: list[ReviewAnswer] = Field(
        ...,
        min_length=1,
    )

    # The dashboard that owns this review. Optional for backward compatibility,
    # but the application sends it for all customer review flows.
    dashboard_id: int | None = None

    # 0 = generated from the dashboard selections, 1 = generated after Regenerate.
    regenerate_status: int = Field(0, ge=0, le=1)


class ReviewResponse(BaseModel):
    success: bool
    review: str
    review_id: int | None = None


class ReviewSubmitStatusRequest(BaseModel):
    submit_status: int = Field(..., ge=0, le=1)
    review_text: str | None = Field(None, max_length=10000)


# =========================================================
# AUTH SCHEMAS
# =========================================================


class SignupRequest(BaseModel):
    business_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
    )

    mobile: str = Field(
        ...,
        min_length=10,
        max_length=20,
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )


class SignupVerifyRequest(BaseModel):
    email: EmailStr

    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
    )


class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        ...,
        min_length=1,
    )


class AuthUserResponse(BaseModel):
    user_id: int
    email_id: EmailStr
    business_name: str
    mobile: str
    is_active: bool


class LoginResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    token_type: str
    user: AuthUserResponse


class MessageResponse(BaseModel):
    success: bool
    message: str


# =========================================================
# BUSINESS INFORMATION SCHEMAS
# =========================================================


class BusinessInfoRequest(BaseModel):
    business_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
    )

    business_type: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )

    about_business: str = Field(
        ...,
        min_length=10,
        max_length=2000,
    )

    year_established: int = Field(
        ...,
        ge=1800,
        le=2100,
    )

    google_review_link: AnyHttpUrl


class BusinessInfoResponse(BaseModel):
    success: bool
    message: str

    business_id: int | None = None
    business_name: str | None = None
    business_type: str | None = None
    about_business: str | None = None
    year_established: int | None = None
    google_review_link: str | None = None
    updated_at: str | None = None
    updated_at_formatted: str | None = None