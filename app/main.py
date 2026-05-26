"""
AI Risk Assessment Agent - FastAPI Application Entry Point

This module bootstraps the FastAPI app, configures middleware,
registers routers, and defines application lifecycle events.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time

# ----------------------------------------------------------------------
# Logging setup (basic for now; we'll upgrade to structlog later)
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ai-risk-agent")


# ----------------------------------------------------------------------
# Lifespan: startup & shutdown hooks
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("🚀 AI Risk Assessment Agent starting up...")
    # TODO: Initialize LangChain LLM client, vector stores, etc.
    yield
    # ---- Shutdown ----
    logger.info("🛑 AI Risk Assessment Agent shutting down...")


# ----------------------------------------------------------------------
# FastAPI app instance
# ----------------------------------------------------------------------
app = FastAPI(
    title="AI Risk Assessment Agent",
    description=(
        "An enterprise-grade agent that assesses AI system risks: "
        "prompt injection, privacy, hallucination, model drift, and compliance gaps."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ----------------------------------------------------------------------
# Middleware: CORS (tighten allow_origins for production)
# ----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # ⚠️ Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Middleware: Request timing & logging
# ----------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} "
        f"-> {response.status_code} ({duration_ms:.2f}ms)"
    )
    response.headers["X-Process-Time-ms"] = f"{duration_ms:.2f}"
    return response


# ----------------------------------------------------------------------
# Global exception handler
# ----------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please contact support.",
        },
    )


# ----------------------------------------------------------------------
# Routes — TEMPORARY inline endpoints
# (We'll move these to app/api/v1/endpoints/ in the next step.)
# ----------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def root():
    """Welcome endpoint."""
    return {
        "service": "AI Risk Assessment Agent",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe for Kubernetes / load balancers."""
    return {"status": "healthy", "service": "ai-risk-agent"}


@app.post("/api/v1/risk/intake", tags=["Risk Assessment"])
async def risk_intake(payload: dict):
    """
    🚧 Placeholder risk intake endpoint.
    Accepts a description of an AI system and returns a stub assessment.
    In the next step we'll add Pydantic schemas and LangChain logic.
    """
    logger.info(f"Received risk intake: {payload}")
    return {
        "received": payload,
        "status": "accepted",
        "message": "Stub response — full risk assessment coming next.",
        "planned_risk_dimensions": [
            "prompt_injection",
            "privacy",
            "hallucination",
            "model_drift",
            "compliance",
        ],
    }


# ----------------------------------------------------------------------
# Local dev entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )