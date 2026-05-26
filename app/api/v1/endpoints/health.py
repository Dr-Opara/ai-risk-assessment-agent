"""
Health check endpoints.

These endpoints are consumed by:
  - Kubernetes liveness/readiness probes
  - Load balancers (AWS ALB, GCP, Azure)
  - Uptime monitoring (Datadog, PagerDuty, etc.)

Keep these endpoints lightweight and dependency-free.
"""

from fastapi import APIRouter, status

from app.schemas.risk import HealthResponse

router = APIRouter(tags=["Health"])

# Service metadata - in production, source these from app.config.settings
SERVICE_NAME = "ai-risk-agent"
SERVICE_VERSION = "0.1.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Returns 200 OK if the service process is alive.",
)
async def health_check() -> HealthResponse:
    """Basic liveness probe - confirms the service is running."""
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Returns 200 OK if the service is ready to handle traffic. "
                "In future iterations, this will validate OpenAI API "
                "connectivity and downstream dependencies.",
)
async def readiness_check() -> HealthResponse:
    """
    Readiness probe - confirms downstream dependencies are reachable.

    TODO: Add checks for:
      - OpenAI API reachability
      - Vector store connectivity (when added)
      - Database connectivity (when added)
    """
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
    )