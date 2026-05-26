"""
API v1 Router Aggregator
-------------------------
Central place to register all v1 endpoint routers.

Why versioning (v1)?
- Allows breaking changes later under /api/v2 without
  disrupting existing clients.
- Standard practice in enterprise REST APIs.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, risk

# Top-level router for API version 1
api_router = APIRouter()

# ---------------------------------------------------------------------
# Register endpoint routers
# ---------------------------------------------------------------------
# Each sub-router handles a single domain concern (separation of concerns).
# Tags are used by Swagger UI (/docs) for grouping endpoints.
# ---------------------------------------------------------------------

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    risk.router,
    prefix="/risk",
    tags=["Risk Assessment"],
)