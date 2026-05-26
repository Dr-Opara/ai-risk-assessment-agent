"""
Hallucination Risk Agent
========================
Detects signals that an LLM system may produce unsupported, fabricated,
or low-confidence outputs.

Scoring is deterministic and heuristic-based today, but the `assess()`
interface is designed to be swapped/augmented with an LLM-based grader
(e.g., LangChain evaluator) in the future without changing callers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "hallucination"

# Lexical signals that often correlate with fabricated or unverified claims.
UNCERTAINTY_MARKERS = [
    r"\bi think\b", r"\bi believe\b", r"\bprobably\b", r"\bmaybe\b",
    r"\bperhaps\b", r"\bmight be\b", r"\bcould be\b", r"\bnot sure\b",
]

# Phrases that imply specific facts that should be grounded in sources.
FACTUAL_CLAIM_MARKERS = [
    r"\baccording to\b", r"\bstudies show\b", r"\bresearch indicates\b",
    r"\bstatistics show\b", r"\bas of \d{4}\b", r"\bin \d{4}\b",
]

# Patterns of fabricated-looking references (e.g., "Smith et al., 2031").
SUSPICIOUS_CITATION = re.compile(
    r"\b[A-Z][a-z]+ et al\.?,?\s*\d{4}\b|\bdoi:\s*10\.\d+/\S+", re.IGNORECASE
)

SEVERITY_THRESHOLDS = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (35, "MEDIUM"),
    (0, "LOW"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _severity_from_score(score: int) -> str:
    """Map a numeric risk score (0-100) to a severity label."""
    for threshold, label in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return label
    return "LOW"


def _count_matches(patterns: List[str], text: str) -> int:
    """Count regex matches across a list of patterns (case-insensitive)."""
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, text, flags=re.IGNORECASE))
    return total


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess hallucination risk for a given LLM output / system description.

    Args:
        payload: {
            "system_description": str,   # what the system does
            "sample_output": str,        # optional model output to grade
            "grounded": bool,            # whether RAG / citations are enforced
            "has_eval_suite": bool,      # whether eval harness exists
        }

    Returns:
        Structured finding dict compatible with risk_assessor.py.
    """
    text = " ".join(
        str(payload.get(k, "")) for k in ("system_description", "sample_output")
    ).strip()

    grounded: bool = bool(payload.get("grounded", False))
    has_evals: bool = bool(payload.get("has_eval_suite", False))

    findings: List[Dict[str, Any]] = []
    score = 0

    # --- Heuristic 1: Uncertainty language ---
    n_uncertain = _count_matches(UNCERTAINTY_MARKERS, text)
    if n_uncertain:
        score += min(20, n_uncertain * 5)
        findings.append({
            "id": "HAL-001",
            "title": "Uncertainty language detected",
            "detail": f"Found {n_uncertain} hedging phrase(s) in output.",
            "weight": min(20, n_uncertain * 5),
        })

    # --- Heuristic 2: Unverifiable factual claims ---
    n_claims = _count_matches(FACTUAL_CLAIM_MARKERS, text)
    if n_claims:
        score += min(25, n_claims * 8)
        findings.append({
            "id": "HAL-002",
            "title": "Unverified factual claims",
            "detail": f"Detected {n_claims} factual assertion(s) without source binding.",
            "weight": min(25, n_claims * 8),
        })

    # --- Heuristic 3: Suspicious citations ---
    if SUSPICIOUS_CITATION.search(text):
        score += 20
        findings.append({
            "id": "HAL-003",
            "title": "Potentially fabricated citation",
            "detail": "Citation-like pattern detected; verify against source corpus.",
            "weight": 20,
        })

    # --- Heuristic 4: Absence of grounding ---
    if not grounded:
        score += 25
        findings.append({
            "id": "HAL-004",
            "title": "No retrieval / grounding layer",
            "detail": "System lacks RAG or citation enforcement — high hallucination surface.",
            "weight": 25,
        })

    # --- Heuristic 5: Absence of evaluation harness ---
    if not has_evals:
        score += 15
        findings.append({
            "id": "HAL-005",
            "title": "No hallucination evaluation suite",
            "detail": "No automated factuality/groundedness evals configured.",
            "weight": 15,
        })

    score = min(score, 100)

    return {
        "agent": AGENT_NAME,
        "score": score,
        "severity": _severity_from_score(score),
        "findings": findings,
        "recommendations": _recommendations(grounded, has_evals, findings),
        "metadata": {
            "heuristic_version": "1.0.0",
            "llm_assisted": False,
        },
    }


def _recommendations(
    grounded: bool, has_evals: bool, findings: List[Dict[str, Any]]
) -> List[str]:
    """Generate concrete, prioritized remediation steps."""
    recs: List[str] = []

    if not grounded:
        recs.append(
            "Introduce a Retrieval-Augmented Generation (RAG) layer with "
            "citation enforcement for factual queries."
        )
    if not has_evals:
        recs.append(
            "Add an automated evaluation suite (e.g., RAGAS, TruLens, or "
            "LangSmith evaluators) covering groundedness and answer relevance."
        )
    if any(f["id"] == "HAL-003" for f in findings):
        recs.append(
            "Implement citation validation against a trusted source index "
            "before returning responses."
        )
    if any(f["id"] in {"HAL-001", "HAL-002"} for f in findings):
        recs.append(
            "Apply a 'refuse-if-unknown' system prompt policy and confidence "
            "scoring thresholds before surfacing answers."
        )

    if not recs:
        recs.append("Maintain current controls; re-run assessment on prompt changes.")
    return recs