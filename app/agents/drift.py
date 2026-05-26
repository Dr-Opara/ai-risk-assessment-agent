"""
Model Drift Risk Agent
======================
Evaluates the likelihood and impact of model drift — including
data drift, concept drift, and provider-side model updates.

Today this is heuristic-based; the interface is stable so future
versions can plug in statistical drift detectors (PSI, KL-divergence)
or LangChain-based evaluators.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

AGENT_NAME = "drift"

SEVERITY_THRESHOLDS = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (35, "MEDIUM"),
    (0, "LOW"),
]


def _severity_from_score(score: int) -> str:
    for threshold, label in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return label
    return "LOW"


def _days_since(iso_date: str | None) -> int | None:
    """Return days elapsed since an ISO date, or None if unparseable."""
    if not iso_date:
        return None
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess model drift risk.

    Args:
        payload: {
            "model_provider": str,            # e.g. "openai", "anthropic", "self-hosted"
            "model_name": str,                # e.g. "gpt-4o"
            "model_version_pinned": bool,     # version locked?
            "last_eval_date": str,            # ISO date of last quality eval
            "monitoring_enabled": bool,       # production telemetry?
            "input_distribution_tracked": bool, # data drift monitoring?
            "feedback_loop": bool,            # user feedback captured?
        }

    Returns:
        Structured finding dict compatible with risk_assessor.py.
    """
    findings: List[Dict[str, Any]] = []
    score = 0

    provider = str(payload.get("model_provider", "")).lower()
    pinned: bool = bool(payload.get("model_version_pinned", False))
    monitoring: bool = bool(payload.get("monitoring_enabled", False))
    dist_tracked: bool = bool(payload.get("input_distribution_tracked", False))
    feedback: bool = bool(payload.get("feedback_loop", False))
    days = _days_since(payload.get("last_eval_date"))

    # --- Heuristic 1: Unpinned model version on managed provider ---
    if provider in {"openai", "anthropic", "google", "azure"} and not pinned:
        score += 25
        findings.append({
            "id": "DRF-001",
            "title": "Model version not pinned",
            "detail": (
                f"Provider '{provider}' may silently update underlying weights. "
                "Pin to a dated snapshot (e.g., gpt-4o-2024-08-06)."
            ),
            "weight": 25,
        })

    # --- Heuristic 2: Stale evaluations ---
    if days is None:
        score += 20
        findings.append({
            "id": "DRF-002",
            "title": "No record of last evaluation",
            "detail": "Unable to determine last evaluation date.",
            "weight": 20,
        })
    elif days > 90:
        score += 25
        findings.append({
            "id": "DRF-002",
            "title": "Stale evaluation cadence",
            "detail": f"Last evaluation was {days} days ago (>90 day threshold).",
            "weight": 25,
        })
    elif days > 30:
        score += 10
        findings.append({
            "id": "DRF-002",
            "title": "Evaluation cadence approaching stale",
            "detail": f"Last evaluation was {days} days ago.",
            "weight": 10,
        })

    # --- Heuristic 3: No production monitoring ---
    if not monitoring:
        score += 20
        findings.append({
            "id": "DRF-003",
            "title": "No production monitoring",
            "detail": "No telemetry on latency, error rates, or output quality.",
            "weight": 20,
        })

    # --- Heuristic 4: No input distribution tracking ---
    if not dist_tracked:
        score += 15
        findings.append({
            "id": "DRF-004",
            "title": "Input distribution not tracked",
            "detail": "Data drift cannot be detected without input distribution baselines.",
            "weight": 15,
        })

    # --- Heuristic 5: No feedback loop ---
    if not feedback:
        score += 15
        findings.append({
            "id": "DRF-005",
            "title": "Missing user feedback loop",
            "detail": "Concept drift will go undetected without user-signal capture.",
            "weight": 15,
        })

    score = min(score, 100)

    return {
        "agent": AGENT_NAME,
        "score": score,
        "severity": _severity_from_score(score),
        "findings": findings,
        "recommendations": _recommendations(findings),
        "metadata": {
            "heuristic_version": "1.0.0",
            "llm_assisted": False,
            "days_since_last_eval": days,
        },
    }


def _recommendations(findings: List[Dict[str, Any]]) -> List[str]:
    recs: List[str] = []
    ids = {f["id"] for f in findings}

    if "DRF-001" in ids:
        recs.append("Pin model to a dated version snapshot in configuration.")
    if "DRF-002" in ids:
        recs.append(
            "Establish a recurring (≤30 day) offline evaluation cadence with "
            "a golden dataset; track quality metrics over time."
        )
    if "DRF-003" in ids:
        recs.append(
            "Deploy production observability (latency, error %, token usage, "
            "output quality) using tools like LangSmith, Arize, or WhyLabs."
        )
    if "DRF-004" in ids:
        recs.append(
            "Baseline production input distributions and alert on PSI / KL "
            "divergence breaches."
        )
    if "DRF-005" in ids:
        recs.append(
            "Capture thumbs-up/down, edit-distance, or downstream task success "
            "signals to detect concept drift."
        )

    if not recs:
        recs.append("Drift controls look healthy; continue scheduled reviews.")
    return recs