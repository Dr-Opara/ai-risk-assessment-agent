"""
Pydantic schemas for AI Risk Assessment.

These models define the request/response contract for the risk assessment API.
All inbound and outbound payloads are validated through these schemas.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskCategory(str, Enum):
    """Supported AI risk categories assessed by the agent."""
    PROMPT_INJECTION = "prompt_injection"
    PRIVACY = "privacy"
    HALLUCINATION = "hallucination"
    MODEL_DRIFT = "model_drift"
    COMPLIANCE = "compliance"


class RiskSeverity(str, Enum):
    """Standardized severity levels (aligned with NIST AI RMF)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssessmentStatus(str, Enum):
    """Lifecycle status of an assessment job."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class RiskAssessmentRequest(BaseModel):
    """
    Inbound payload for a new AI risk assessment.

    Clients submit a description of the AI system / use case and optionally
    narrow the scope to specific risk categories.
    """

    system_name: str = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Human-readable name of the AI system under review.",
    )
    system_description: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Detailed description of the AI system, its purpose, "
                    "data sources, model(s), and user base.",
    )
    intended_use_case: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Specific business use case (e.g., 'customer support chatbot').",
    )
    data_sensitivity: Optional[str] = Field(
        default="unknown",
        description="Sensitivity of data processed (public, internal, "
                    "confidential, regulated).",
    )
    categories: Optional[List[RiskCategory]] = Field(
        default=None,
        description="Optional subset of risk categories to assess. "
                    "If omitted, all categories are evaluated.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "system_name": "SupportBot-GPT",
                "system_description": (
                    "An LLM-based customer support assistant that uses GPT-4 "
                    "with RAG over internal knowledge base articles. Handles "
                    "billing inquiries and product troubleshooting. Integrated "
                    "with CRM and exposes a public-facing chat widget."
                ),
                "intended_use_case": "External customer support automation",
                "data_sensitivity": "confidential",
                "categories": [
                    "prompt_injection",
                    "privacy",
                    "hallucination",
                ],
            }
        }
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class RiskFinding(BaseModel):
    """Single finding within a risk category."""

    category: RiskCategory
    severity: RiskSeverity
    score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Numeric risk score (0.0 = no risk, 10.0 = critical).",
    )
    summary: str = Field(..., description="One-line summary of the finding.")
    details: str = Field(..., description="Detailed analysis and reasoning.")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable mitigation recommendations.",
    )


class RiskAssessmentResponse(BaseModel):
    """Outbound payload returned after a risk assessment."""

    assessment_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this assessment.",
    )
    system_name: str
    status: AssessmentStatus
    overall_severity: Optional[RiskSeverity] = None
    overall_score: Optional[float] = Field(
        default=None, ge=0.0, le=10.0,
        description="Aggregated risk score across all categories.",
    )
    findings: List[RiskFinding] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assessment_id": "8b1a2c34-5d6e-7f89-90ab-cdef12345678",
                "system_name": "SupportBot-GPT",
                "status": "completed",
                "overall_severity": "high",
                "overall_score": 7.4,
                "findings": [
                    {
                        "category": "prompt_injection",
                        "severity": "high",
                        "score": 8.1,
                        "summary": "Public-facing chat lacks input sanitization.",
                        "details": "The system accepts unstructured user input "
                                   "directly into the prompt without delimiter "
                                   "guards or instruction hierarchy enforcement.",
                        "recommendations": [
                            "Implement input validation and sanitization.",
                            "Adopt OpenAI's instruction hierarchy pattern.",
                            "Add a prompt-injection classifier in front of the LLM.",
                        ],
                    }
                ],
                "created_at": "2025-01-15T10:30:00Z",
            }
        }
    )


# ---------------------------------------------------------------------------
# Health Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Standardized health check response."""

    status: str = Field(..., description="'ok' if the service is healthy.")
    service: str = Field(..., description="Service identifier.")
    version: str = Field(..., description="Service version (semver).")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "ai-risk-agent",
                "version": "0.1.0",
                "timestamp": "2025-01-15T10:30:00Z",
            }
        }
    )