from fastapi import APIRouter

from app.routers.v1.admin import router as admin_router
from app.routers.v1.attempts import router as attempts_router
from app.routers.v1.auth import router as auth_router
from app.routers.v1.documents import router as documents_router
from app.routers.v1.quizzes import router as quizzes_router
from app.routers.v1.subjects import router as subjects_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(subjects_router)
api_router.include_router(quizzes_router)
api_router.include_router(attempts_router)
api_router.include_router(documents_router)
api_router.include_router(admin_router)
