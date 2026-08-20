import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.responses import success_response
from app.middleware.rate_limit import limiter
from app.routers.v1 import api_router

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)

app = FastAPI(
    title="MveousQuiz API",
    description="AI-powered Exam Intelligence Platform — MVP slice",
    version="0.1.0",
    debug=settings.debug,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return success_response(data={"status": "ok", "environment": settings.environment})
