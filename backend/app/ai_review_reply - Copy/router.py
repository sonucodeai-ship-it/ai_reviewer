from fastapi import APIRouter

from .google_routes import router as google_router
from .review_routes import router as review_router

router = APIRouter()
router.include_router(google_router)
router.include_router(review_router)
