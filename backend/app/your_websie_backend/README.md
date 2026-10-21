# Your Own Product Website

This feature is intentionally isolated from the existing `pages` and backend modules.

## Frontend

Copy:

`frontend/src/your_website_frontend/`

to:

`D:\visualgrab_app\review_app - Copy\frontend\src\your_website_frontend\`

## Backend

Copy:

`backend/app/your_websie_backend/`

to:

`D:\visualgrab_app\review_app - Copy\backend\app\your_websie_backend\`

## Database

Run:

`database/your_website_schema.sql`

against the existing `ai_reviewer` database.

## Existing files that must be updated

1. `frontend/src/pages/Menu/menu.jsx`
   - Add the `Your Own Product Website` card.
   - Navigate to `/your-website`.

2. `frontend/src/App.jsx`
   - Import `YourWebsite` and `WebsitePreview`.
   - Add:
     - `/your-website`
     - `/your-website/preview/:publicUrlId`

3. `backend/app/main.py`
   - Import:
     `from app.your_websie_backend.router import router as your_website_router`
   - Register:
     `app.include_router(your_website_router)`

## Gemini environment variable

The new backend service expects:

`GEMINI_API_KEY`

Optional:

`GEMINI_WEBSITE_MODEL`

If `GEMINI_WEBSITE_MODEL` is not supplied, it falls back to `GEMINI_MODEL`, then `gemini-2.5-flash-lite`.

The feature uses Gemini only to generate structured JSON content. React renders the website using controlled components rather than executing AI-generated HTML/CSS/JS.

## Workflow

Menu
→ Your Own Product Website
→ Read business_info
→ AI generates business-specific questions
→ User answers questions
→ AI generates website configuration
→ Configuration is saved
→ Public website is available at:

`/your-website/preview/<public_url_id>`

The API also exposes the public data at:

`GET /api/your-website/public/<public_url_id>`


## Dependency

If the existing backend environment does not already contain the Gemini SDK:

```powershell
pip install google-generativeai
```

The API key remains backend-only.
