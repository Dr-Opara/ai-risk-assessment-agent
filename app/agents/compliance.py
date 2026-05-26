"""
Compliance Gap Agent
====================
Maps detected control weaknesses to industry frameworks:

- NIST AI Risk Management Framework (AI RMF 1.0)
- OWASP Top 10 for LLM Applications (2025)
- NIST SP 800-53 Rev. 5

This agent operates on the *aggregated outputs* of upstream agents
(hallucination, drift, privacy, prompt_injection) AND on system-level
controls declared in the payload. It is intentionally framework-aware
so it can be consumed by GRC tooling downstream.
"""

from __future__ import annotations

from typing import Any, Dict, List

AGENT_NAME = "compliance"

SEVERITY_THRESHOLDS = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (35, "MEDIUM"),
    (0, "LOW"),
]


# ---------------------------------------------------------------------------
# Control catalog: each control maps to upstream signals + framework refs.
# ---------------------------------------------------------------------------

CONTROL_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "CMP-001",
        "title": "Input validation & prompt-injection defenses",
        "trigger_agents": ["prompt_injection"],
        "trigger_severity": {"HIGH", "CRITICAL"},
        "weight": 20,
        "frameworks": {
            "NIST_AI_RMF": ["MANAGE-2.1", "MEASURE-2.6"],
            "OWASP_LLM": ["LLM01: Prompt Injection"],
            "NIST_800_53": ["SI-10", "SC-7"],
        },
        "recommendation": (
            "Implement structured input validation, allow-lists, and a "
            "prompt-injection classifier on user-supplied content."
        ),
    },
    {
        "id": "CMP-002",
        "title": "Sensitive data protection in LLM I/O",
        "trigger_agents": ["privacy"],
        "trigger_severity": {"MEDIUM", "HIGH", "CRITICAL"},
        "weight": 20,
        "frameworks": {
            "NIST_AI_RMF": ["GOVERN-1.1", "MAP-4.1"],
            "OWASP_LLM": ["LLM02: Sensitive Information Disclosure"],
            "NIST_800_53": ["AC-3", "SC-28", "MP-6"],
        },
        "recommendation": (
            "Apply PII redaction at ingress/egress, enforce data minimization, "
            "and ensure no sensitive data is logged in prompts/completions."
        ),
    },
    {
        "id": "CMP-003",
        "title": "Output groundedness & hallucination controls",
        "trigger_agents": ["hallucination"],
        "trigger_severity": {"MEDIUM", "HIGH", "CRITICAL"},
        "weight": 15,
        "frameworks": {
            "NIST_AI_RMF": ["MEASURE-2.3", "MEASURE-2.5"],
            "OWASP_LLM": ["LLM09: Misinformation"],
            "NIST_800_53": ["SI-7", "CA-7"],
        },
        "recommendation": (
            "Mandate RAG + citation enforcement and continuous factuality "
            "evaluation for production LLM responses."
        ),
    },
    {
        "id": "CMP-004",
        "title": "Model lifecycle & drift monitoring",
        "trigger_agents": ["drift"],
        "trigger_severity": {"MEDIUM", "HIGH", "CRITICAL"},
        "weight": 15,
        "frameworks": {
            "NIST_AI_RMF": ["MANAGE-4.1", "MEASURE-2.4"],
            "OWASP_LLM": ["LLM05: Improper Output Handling"],
            "NIST_800_53": ["CM-3", "CM-8", "CA-7"],
        },
        "recommendation": (
            "Pin model versions, run scheduled evaluations, and alert on "
            "distribution drift in production telemetry."
        ),
    },
    {
        "id": "CMP-005",
        "title": "Human oversight & accountability",
        "trigger_field": "human_in_the_loop",
        "expected_value": True,
        "weight": 10,
        "frameworks": {
            "NIST_AI_RMF": ["GOVERN-2.1", "GOVERN-3.2"],
            "OWASP_LLM": ["LLM08: Excessive Agency"],
            "NIST_800_53": ["PM-29", "AC-2"],
        },
        "recommendation": (
            "Define human-in-the-loop checkpoints for high-impact decisions "
            "and document accountable owners."
        ),
    },
    {
        "id": "CMP-006",
        "title": "Audit logging of AI interactions",
        "trigger_field": "audit_logging",
        "expected_value": True,
        "weight": 10,
        "frameworks": {
            "NIST_AI_RMF": ["GOVERN-1.2", "MEASURE-3.1"],
            "OWASP_LLM": ["LLM05: Improper Output Handling"],
            "NIST_800_53": ["AU-2", "AU-3", "AU-12"],
        },
        "recommendation": (
            "Log prompts, completions, model versions, and user identifiers "
            "with tamper-evident storage and retention policies."
        ),
    },
    {
        "id": "CMP-007",
        "title": "Documented AI risk policy",
        "trigger_field": "risk_policy_documented",
        "expected_value": True,
        "weight": 10,
        "frameworks": {
            "NIST_AI_RMF": ["GOVERN-1.1"],
            "OWASP_LLM": ["LLM10: Unbounded Consumption"],
            "NIST_800_53": ["PM-9", "RA-1"],
        },
        "recommendation": (
            "Publish and version-control an AI risk management policy, "
            "including acceptable-use and incident-response procedures."
        ),
    },
]


def _severity_from_score(score: int) -> str:
    for threshold, label in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return label
    return "LOW"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess compliance gaps against NIST AI RMF, OWASP LLM Top 10, and NIST 800-53.

    Args:
        payload: {
            "controls": {
                "human_in_the_loop": bool,
                "audit_logging": bool,
                "risk_policy_documented": bool,
            },
            "upstream_results": [
                { "agent": "hallucination", "severity": "HIGH", ... },
                { "agent": "drift",         "severity": "LOW",  ... },
                ...
            ],
        }

    Returns:
        Structured finding dict, including framework mappings, compatible
        with risk_assessor.py.
    """
    controls: Dict[str, Any] = payload.get("controls", {}) or {}
    upstream: List[Dict[str, Any]] = payload.get("upstream_results", []) or []

    upstream_by_agent: Dict[str, Dict[str, Any]] = {
        r.get("agent"): r for r in upstream if isinstance(r, dict)
    }

    findings: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    score = 0
    framework_hits: Dict[str, List[str]] = {
        "NIST_AI_RMF": [],
        "OWASP_LLM": [],
        "NIST_800_53": [],
    }

    for control in CONTROL_CATALOG:
        triggered = False
        detail = ""

        # ----- Path A: triggered by an upstream agent's severity -----
        if "trigger_agents" in control:
            for agent_name in control["trigger_agents"]:
                result = upstream_by_agent.get(agent_name)
                if result and result.get("severity") in control["trigger_severity"]:
                    triggered = True
                    detail = (
                        f"Upstream agent '{agent_name}' reported severity "
                        f"{result.get('severity')}."
                    )
                    break

        # ----- Path B: triggered by missing declared control -----
        elif "trigger_field" in control:
            actual = controls.get(control["trigger_field"])
            if actual != control["expected_value"]:
                triggered = True
                detail = (
                    f"Control '{control['trigger_field']}' is "
                    f"{actual!r}; expected {control['expected_value']!r}."
                )

        if not triggered:
            continue

        # Accumulate score
        score += control["weight"]

        # Record finding with framework mappings
        findings.append({
            "id": control["id"],
            "title": control["title"],
            "detail": detail,
            "weight": control["weight"],
            "frameworks": control["frameworks"],
        })

        recommendations.append(control["recommendation"])

        # Aggregate framework hits (deduplicated)
        for fw, refs in control["frameworks"].items():
            for ref in refs:
                if ref not in framework_hits[fw]:
                    framework_hits[fw].append(ref)

    score = min(score, 100)

    if not recommendations:
        recommendations.append(
            "No compliance gaps detected against current control set."
        )

    return {
        "agent": AGENT_NAME,
        "score": score,
        "severity": _severity_from_score(score),
        "findings": findings,
        "recommendations": recommendations,
        "metadata": {
            "heuristic_version": "1.0.0",
            "llm_assisted": False,
            "frameworks_triggered": framework_hits,
            "controls_evaluated": len(CONTROL_CATALOG),
            "controls_failed": len(findings),
        },
    }