"""
Risk Assessment Orchestrator
----------------------------
Coordinates all risk agents and aggregates their results into a single
RiskAssessmentResponse. Designed for dependency injection from FastAPI.

LLM/LangChain orchestration is intentionally NOT here yet — this layer
currently runs deterministic agents only. When you add LLM agents,
register them the same way (they must expose `.assess()` returning
an AgentResult).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

from app.agents.privacy import PrivacyAgent
from app.agents.prompt_injection import PromptInjectionAgent
from app.schemas.risk import (
    AgentResult,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    Severity,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent contract
# ---------------------------------------------------------------------------
class RiskAgent(Protocol):
    """Structural contract every risk agent must satisfy."""

    CATEGORY: str

    def assess(self, prompt: str, context: str | None = None) -> AgentResult: ...


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class RiskAssessor:
    """Runs all registered risk agents and aggregates findings."""

    def __init__(self, agents: list[RiskAgent] | None = None) -> None:
        # Default agent registry — extend here as new agents are built
        self.agents: list[RiskAgent] = agents or [
            PromptInjectionAgent(),
            PrivacyAgent(),
            # HallucinationAgent(),   # coming next
            # DriftAgent(),
            # ComplianceAgent(),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def assess(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        logger.info(
            "Starting risk assessment | agents=%d | prompt_len=%d",
            len(self.agents),
            len(request.prompt or ""),
        )

        results: list[AgentResult] = []
        for agent in self.agents:
            try:
                result = agent.assess(request.prompt, request.context)
                results.append(result)
            except Exception as exc:  # never fail the whole assessment
                logger.exception("Agent %s failed: %s", agent.CATEGORY, exc)
                results.append(self._failed_result(agent.CATEGORY, str(exc)))

        overall_score = self._aggregate_score(results)
        overall_severity = self._overall_severity(overall_score)

        response = RiskAssessmentResponse(
            overall_score=round(overall_score, 2),
            overall_severity=overall_severity,
            results=results,
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "Assessment complete | score=%.2f | severity=%s",
            response.overall_score,
            response.overall_severity,
        )
        return response

    # ------------------------------------------------------------------
    # Aggregation logic
    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate_score(results: list[AgentResult]) -> float:
        """
        Weighted aggregation:
        - Take the max single-agent score (worst-case domain)
        - Add a small bonus for breadth (multiple agents triggered)
        This avoids diluting a critical finding by averaging.
        """
        if not results:
            return 0.0

        scores = [r.risk_score for r in results]
        max_score = max(scores)
        triggered = sum(1 for s in scores if s > 0)
        breadth_bonus = min((triggered - 1) * 5.0, 15.0) if triggered > 1 else 0.0
        return min(max_score + breadth_bonus, 100.0)

    @staticmethod
    def _overall_severity(score: float) -> Severity:
        if score >= 75:
            return Severity.CRITICAL
        if score >= 50:
            return Severity.HIGH
        if score >= 25:
            return Severity.MEDIUM
        if score > 0:
            return Severity.LOW
        return Severity.NONE

    @staticmethod
    def _failed_result(category: str, error: str) -> AgentResult:
        return AgentResult(
            category=category,
            risk_score=0.0,
            severity=Severity.NONE,
            findings=[],
            recommendations=[f"Agent execution failed: {error}"],
        )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_risk_assessor() -> RiskAssessor:
    """FastAPI dependency provider. Swap easily in tests via app.dependency_overrides."""
    return RiskAssessor()