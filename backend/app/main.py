from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Reproute API", version="0.1.0")

# Hardcoded CORS origins - bypassing env var issues
cors_origins = [
    "https://reproute-8vhf.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    """Root endpoint — handles both GET and HEAD for Render health checks."""
    return {"status": "ok", "service": "reproute-api"}

app.include_router(api_router)
