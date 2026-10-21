import os

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
GOOGLE_OAUTH_REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "http://127.0.0.1:8000/api/ai-review-reply/google/callback",
).strip()
GOOGLE_FRONTEND_URL = os.getenv("GOOGLE_FRONTEND_URL", "http://localhost:5173").strip()
GOOGLE_BUSINESS_SCOPE = "https://www.googleapis.com/auth/business.manage"
GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ACCOUNT_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
GOOGLE_LOCATION_API = "https://mybusinessbusinessinformation.googleapis.com/v1"
OAUTH_STATE_MINUTES = int(os.getenv("GOOGLE_OAUTH_STATE_MINUTES", "10"))
GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY", "").strip()
