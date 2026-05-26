"""
Risk Assessor Service
---------------------
Orchestrates the multi-agent AI risk assessment pipeline.

This service is the single entry point used by the API layer (`app/api/v1/endpoints/risk.py`)
to run a full assessment across all risk dimensions:

    1. Prompt Injection Risk
    2. Privacy Risk
    3. Hallucination Risk
    4. Model Drift Risk
    5. Compliance Gaps

Design principles:
    - Stateless service (safe for concurrent requests)
    - Async-first (parallel agent execution)
    - Fail-soft (one agent failure does not kill the assessment)
    - Structured logging for observability
    - LLM client injected (testable, swappable)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import structlog
from langchain_openai import ChatOpenAI

from app.agents.compliance import ComplianceAgent
from app.agents.drift import DriftAgent
from app.agents.hallucination import HallucinationAgent
from app.agents.privacy import PrivacyAgent
from app.agents.prompt_injection import PromptInjectionAgent
from app.config import settings
from app.schemas.risk import (
    AgentResult,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    RiskLevel,
)

logger = structlog.get_logger(__name__)


class RiskAssessorService:
    """
    Coordinates all risk-analysis agents and produces a unified assessment report.

    Usage:
        service = RiskAssessorService()
        report = await service.assess(request)
    """

    # Weighted contribution of each risk dimension to the overall score (0–100).
    # Tune these based on your enterprise risk appetite.
    RISK_WEIGHTS: dict[str, float] = {
        "prompt_injection": 0.25,
        "privacy": 0.25,
        "hallucination": 0.20,
        "drift": 0.15,
        "compliance": 0.15,
    }

    def __init__(self, llm: ChatOpenAI | None = None) -> None:
        # Single LLM instance is shared across agents for connection reuse.
        self.llm = llm or ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT,
            max_retries=2,
        )

        # Instantiate agents once. Agents are expected to expose:
        #     async def analyze(self, request: RiskAssessmentRequest) -> AgentResult
        self.agents: dict[str, Any] = {
            "prompt_injection": PromptInjectionAgent(self.llm),
            "privacy": PrivacyAgent(self.llm),
            "hallucination": HallucinationAgent(self.llm),
            "drift": DriftAgent(self.llm),
            "compliance": ComplianceAgent(self.llm),
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def assess(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """
        Run the full risk assessment pipeline.

        All agents execute concurrently. A failure in one agent is captured
        and reported but does NOT abort the rest of the assessment.
        """
        assessment_id = str(uuid.uuid4())
        started = time.perf_counter()

        log = logger.bind(
            assessment_id=assessment_id,
            system_name=request.system_name,
        )
        log.info("risk_assessment.started", agents=list(self.agents.keys()))

        # Run all agents in parallel
        results = await asyncio.gather(
            *[self._run_agent(name, agent, request) for name, agent in self.agents.items()],
            return_exceptions=False,  # _run_agent already handles exceptions
        )

        agent_results: dict[str, AgentResult] = {r.dimension: r for r in results}

        overall_score = self._compute_overall_score(agent_results)
        overall_level = self._score_to_level(overall_score)
        summary = self._build_summary(agent_results, overall_score)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "risk_assessment.completed",
            overall_score=overall_score,
            overall_level=overall_level.value,
            elapsed_ms=elapsed_ms,
        )

        return RiskAssessmentResponse(
            assessment_id=assessment_id,
            system_name=request.system_name,
            overall_score=overall_score,
            overall_level=overall_level,
            summary=summary,
            results=agent_results,
            elapsed_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    async def _run_agent(
        self,
        name: str,
        agent: Any,
        request: RiskAssessmentRequest,
    ) -> AgentResult:
        """Run a single agent with fail-soft error handling."""
        log = logger.bind(agent=name)
        start = time.perf_counter()
        try:
            result = await agent.analyze(request)
            log.info(
                "agent.completed",
                score=result.score,
                level=result.level.value,
                elapsed_ms=int((time.perf_counter() - start) * 1000),
            )
            return result
        except Exception as exc:  # noqa: BLE001 — we intentionally catch all
            log.exception("agent.failed", error=str(exc))
            return AgentResult(
                dimension=name,
                score=0.0,
                level=RiskLevel.UNKNOWN,
                findings=[],
                recommendations=[],
                error=f"{type(exc).__name__}: {exc}",
            )

    def _compute_overall_score(self, results: dict[str, AgentResult]) -> float:
        """
        Weighted average of agent scores.
        Agents that errored (UNKNOWN) are excluded from the weighting, and the
        remaining weights are renormalized so a partial outage doesn't artificially
        deflate the score.
        """
        total_weight = 0.0
        weighted_sum = 0.0
        for dim, weight in self.RISK_WEIGHTS.items():
            result = results.get(dim)
            if result is None or result.level == RiskLevel.UNKNOWN:
                continue
            weighted_sum += result.score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight, 2)

    @staticmethod
    def _score_to_level(score: float) -> RiskLevel:
        """Map a 0–100 risk score to a categorical level."""
        if score >= 75:
            return RiskLevel.CRITICAL
        if score >= 50:
            return RiskLevel.HIGH
        if score >= 25:
            return RiskLevel.MEDIUM
        if score > 0:
            return RiskLevel.LOW
        return RiskLevel.UNKNOWN

    @staticmethod
    def _build_summary(results: dict[str, AgentResult], overall_score: float) -> str:
        """Produce a short human-readable summary for dashboards/reports."""
        top = sorted(
            (r for r in results.values() if r.level != RiskLevel.UNKNOWN),
            key=lambda r: r.score,
            reverse=True,
        )[:3]

        if not top:
            return "No risk signals could be computed. Review agent errors."

        highlights = ", ".join(f"{r.dimension} ({r.score:.0f})" for r in top)
        return (
            f"Overall risk score: {overall_score:.0f}/100. "
            f"Top concerns: {highlights}."
        )


# Module-level singleton — FastAPI dependency injection will use this.
risk_assessor_service = RiskAssessorService()