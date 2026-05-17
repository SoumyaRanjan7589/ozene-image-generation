from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.v1.routes.generate import router as generate_router

# settings = Settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-powered image compositing API using fal.ai",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_router, prefix="/api/v1", tags=["Generation"])


@app.get("/api/v1/health", tags=["Health"])
async def health():
    return JSONResponse(
        content={
            "success": True,
            "code": 200,
            "message": "Service is running",
            "data": {
                "app": settings.APP_NAME,
                "version": settings.VERSION,
                "model": settings.FAL_MODEL,
            },
        }
    )