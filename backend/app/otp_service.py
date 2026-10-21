import os
import secrets
import smtplib

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from dotenv import load_dotenv


# =========================================================
# ENVIRONMENT CONFIGURATION
# =========================================================

load_dotenv()


# OTP validity duration
OTP_EXPIRE_MINUTES = int(
    os.getenv("OTP_EXPIRE_MINUTES", "10")
)


# =========================================================
# OTP GENERATION
# =========================================================

def generate_otp() -> str:
    """
    Generate a secure 6-digit OTP.

    Returns:
        str: Six-digit verification code.
    """

    return f"{secrets.randbelow(1_000_000):06d}"


# =========================================================
# SEND SIGNUP OTP EMAIL
# =========================================================

def send_signup_otp(
    email: str,
    business_name: str,
    otp: str,
):
    """
    Send a professional HTML signup verification email.

    Args:
        email: Recipient email address.
        business_name: Business name entered during signup.
        otp: Six-digit verification code.

    Raises:
        RuntimeError: If SMTP credentials are missing.
        Exception: If the email cannot be sent.
    """

    # -----------------------------------------------------
    # SMTP configuration
    # -----------------------------------------------------

    smtp_server = os.getenv(
        "SMTP_SERVER",
        "smtp.gmail.com",
    )

    smtp_port = int(
        os.getenv(
            "SMTP_PORT",
            "587",
        )
    )

    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    # -----------------------------------------------------
    # Validate SMTP credentials
    # -----------------------------------------------------

    if not smtp_email or not smtp_password:
        raise RuntimeError(
            "SMTP_EMAIL and SMTP_PASSWORD are required."
        )

    # =====================================================
    # EMAIL CONTENT
    # =====================================================

    subject = "AI Reviewer - Verify Your Email"

    # -----------------------------------------------------
    # Plain-text fallback
    #
    # This is used by email clients that do not support
    # HTML emails.
    # -----------------------------------------------------

    text_content = f"""
Hello {business_name},

Welcome to AI Reviewer.

To complete your account registration, please use the
verification code below:

{otp}

This verification code will expire in {OTP_EXPIRE_MINUTES} minutes.

If you did not request this verification, you can safely
ignore this email. No action is required.

Regards,
AI Reviewer
"""

    # -----------------------------------------------------
    # Professional HTML email
    # -----------------------------------------------------

    html_content = f"""
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>AI Reviewer - Email Verification</title>
</head>

<body
    style="
        margin:0;
        padding:0;
        background-color:#f4f7fb;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            'Segoe UI',
            Arial,
            sans-serif;
    "
>

    <!-- Main background -->
    <table
        width="100%"
        cellpadding="0"
        cellspacing="0"
        border="0"
        style="
            background-color:#f4f7fb;
            padding:40px 15px;
        "
    >

        <tr>
            <td align="center">

                <!-- Email container -->
                <table
                    width="100%"
                    cellpadding="0"
                    cellspacing="0"
                    border="0"
                    style="
                        max-width:520px;
                        background-color:#ffffff;
                        border-radius:14px;
                        overflow:hidden;
                        box-shadow:
                            0 8px 30px rgba(15, 23, 42, 0.08);
                    "
                >

                    <!-- ================================= -->
                    <!-- HEADER -->
                    <!-- ================================= -->

                    <tr>
                        <td
                            align="center"
                            style="
                                background-color:#2563eb;
                                padding:28px 25px;
                            "
                        >

                            <div
                                style="
                                    color:#ffffff;
                                    font-size:25px;
                                    font-weight:700;
                                    letter-spacing:0.3px;
                                "
                            >
                                AI Reviewer
                            </div>

                            <div
                                style="
                                    color:#dbeafe;
                                    font-size:13px;
                                    margin-top:7px;
                                "
                            >
                                Smart Reviews. Simple Experience.
                            </div>

                        </td>
                    </tr>


                    <!-- ================================= -->
                    <!-- BODY -->
                    <!-- ================================= -->

                    <tr>
                        <td
                            style="
                                padding:38px 35px 30px;
                                color:#1f2937;
                            "
                        >

                            <!-- Greeting -->

                            <p
                                style="
                                    margin:0 0 8px;
                                    font-size:18px;
                                    font-weight:600;
                                    color:#111827;
                                "
                            >
                                Hello {business_name},
                            </p>


                            <p
                                style="
                                    margin:0 0 18px;
                                    font-size:15px;
                                    line-height:1.7;
                                    color:#4b5563;
                                "
                            >
                                Welcome to AI Reviewer.
                                We received a request to create
                                your account. Please verify your
                                email address using the verification
                                code below.
                            </p>


                            <!-- ================================= -->
                            <!-- OTP SECTION -->
                            <!-- ================================= -->

                            <div
                                style="
                                    margin:28px 0;
                                    padding:24px 20px;
                                    background-color:#f8faff;
                                    border:1px solid #dbeafe;
                                    border-radius:12px;
                                    text-align:center;
                                "
                            >

                                <div
                                    style="
                                        font-size:12px;
                                        font-weight:600;
                                        color:#64748b;
                                        text-transform:uppercase;
                                        letter-spacing:1.2px;
                                        margin-bottom:12px;
                                    "
                                >
                                    Verification Code
                                </div>


                                <div
                                    style="
                                        display:inline-block;
                                        padding:14px 24px;
                                        background-color:#ffffff;
                                        border:1px solid #bfdbfe;
                                        border-radius:9px;
                                        color:#1e3a8a;
                                        font-size:30px;
                                        line-height:1;
                                        font-weight:700;
                                        letter-spacing:7px;
                                        font-family:
                                            'Segoe UI',
                                            Arial,
                                            sans-serif;
                                    "
                                >
                                    {otp}
                                </div>


                                <div
                                    style="
                                        margin-top:14px;
                                        font-size:13px;
                                        color:#64748b;
                                    "
                                >
                                    This code expires in
                                    <strong>
                                        {OTP_EXPIRE_MINUTES} minutes
                                    </strong>.
                                </div>

                            </div>


                            <!-- ================================= -->
                            <!-- SECURITY MESSAGE -->
                            <!-- ================================= -->

                            <div
                                style="
                                    margin-top:25px;
                                    padding:15px 16px;
                                    background-color:#f8fafc;
                                    border-left:4px solid #2563eb;
                                    border-radius:5px;
                                "
                            >

                                <p
                                    style="
                                        margin:0;
                                        font-size:13px;
                                        line-height:1.6;
                                        color:#64748b;
                                    "
                                >
                                    <strong style="color:#374151;">
                                        Security notice:
                                    </strong>

                                    Never share this verification
                                    code with anyone. AI Reviewer
                                    will never ask you to share your
                                    OTP.
                                </p>

                            </div>


                            <!-- ================================= -->
                            <!-- UNREQUESTED EMAIL -->
                            <!-- ================================= -->

                            <p
                                style="
                                    margin:25px 0 0;
                                    font-size:13px;
                                    line-height:1.6;
                                    color:#9ca3af;
                                "
                            >
                                If you did not request this
                                verification, you can safely ignore
                                this email. Your account remains
                                secure.
                            </p>

                        </td>
                    </tr>


                    <!-- ================================= -->
                    <!-- FOOTER -->
                    <!-- ================================= -->

                    <tr>
                        <td
                            align="center"
                            style="
                                background-color:#f8fafc;
                                border-top:1px solid #eef2f7;
                                padding:20px 25px;
                            "
                        >

                            <div
                                style="
                                    font-size:13px;
                                    font-weight:600;
                                    color:#475569;
                                    margin-bottom:6px;
                                "
                            >
                                AI Reviewer
                            </div>

                            <div
                                style="
                                    font-size:11px;
                                    line-height:1.5;
                                    color:#94a3b8;
                                "
                            >
                                This is an automated message.
                                Please do not reply to this email.
                            </div>

                            <div
                                style="
                                    margin-top:8px;
                                    font-size:11px;
                                    color:#cbd5e1;
                                "
                            >
                                © AI Reviewer. All rights reserved.
                            </div>

                        </td>
                    </tr>

                </table>

            </td>
        </tr>

    </table>

</body>

</html>
"""

    # =====================================================
    # CREATE EMAIL
    # =====================================================

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = smtp_email
    message["To"] = email

    # Plain-text version
    message.set_content(text_content)

    # HTML version
    message.add_alternative(
        html_content,
        subtype="html",
    )

    # =====================================================
    # SEND EMAIL
    # =====================================================

    try:
        with smtplib.SMTP(
            smtp_server,
            smtp_port,
        ) as server:

            # Secure the SMTP connection
            server.starttls()

            # Authenticate
            server.login(
                smtp_email,
                smtp_password,
            )

            # Send email
            server.send_message(message)

    except Exception as error:

        print(
            f"SMTP ERROR: {error}"
        )

        raise RuntimeError(
            "Failed to send signup verification email."
        ) from error


# =========================================================
# OTP EXPIRY
# =========================================================

def get_otp_expiry() -> datetime:
    """
    Return the UTC expiration time for a newly generated OTP.

    Returns:
        datetime: OTP expiration timestamp in UTC.
    """

    return (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=OTP_EXPIRE_MINUTES
        )
    )