"""
Risk Assessment endpoints.

These endpoints accept AI system descriptions and return structured risk
assessments across five categories:
  - Prompt injection
  - Privacy
  - Hallucination
  - Model drift
  - Compliance gaps

Note: The current implementation returns a stub response. The LangChain-
powered service layer (app/services/risk_assessor.py) will be wired in
the next iteration.
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas.risk import (
    AssessmentStatus,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)

router = APIRouter(prefix="/risk", tags=["Risk Assessment"])


@router.post(
    "/assess",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit an AI system for risk assessment",
    description=(
        "Accepts a description of an AI system and returns a multi-category "
        "risk assessment. If `categories` is omitted, all risk categories "
        "are evaluated."
    ),
    responses={
        200: {"description": "Assessment completed successfully."},
        422: {"description": "Validation error in request payload."},
        500: {"description": "Internal server error during assessment."},
    },
)
async def assess_risk(payload: RiskAssessmentRequest) -> RiskAssessmentResponse:
    """
    Submit an AI system for risk assessment.

    The current implementation is a stub that returns a placeholder response.
    In the next iteration, this will:
      1. Delegate to `RiskAssessorService` (LangChain orchestration)
      2. Fan out to specialized agents per risk category
      3. Aggregate findings into a normalized response
    """
    try:
        # Determine which categories to assess (default: all)
        selected_categories = payload.categories or list(RiskCategory)

        # ----- STUB IMPLEMENTATION -----
        # TODO: Replace with `await risk_assessor_service.run(payload)`
        stub_findings = [
            RiskFinding(
                category=cat,
                severity=RiskSeverity.MEDIUM,
                score=5.0,
                summary=f"Stubbed {cat.value} assessment.",
                details=(
                    f"This is a placeholder finding for category '{cat.value}'. "
                    "The LangChain-powered analyzer has not yet been wired in."
                ),
                recommendations=[
                    "Wire up the LangChain agent in app/services/risk_assessor.py",
                ],
            )
            for cat in selected_categories
        ]

        return RiskAssessmentResponse(
            system_name=payload.system_name,
            status=AssessmentStatus.COMPLETED,
            overall_severity=RiskSeverity.MEDIUM,
            overall_score=5.0,
            findings=stub_findings,
        )

    except Exception as exc:
        # In production, swap for structlog with correlation IDs
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk assessment failed: {exc!s}",
        ) from exc


@router.get(
    "/categories",
    response_model=list[str],
    summary="List supported risk categories",
    description="Returns the set of risk categories this agent can assess.",
)
async def list_categories() -> list[str]:
    """Returns all supported risk category identifiers."""
    return [c.value for c in RiskCategory]