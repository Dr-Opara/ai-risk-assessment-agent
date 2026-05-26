"""
Prompt Injection Risk Agent
---------------------------
Deterministic heuristic detector for prompt-injection patterns.
LLM-based scoring will be layered in later via LangChain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.risk import AgentResult, Finding, Severity


# ---------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InjectionRule:
    name: str
    pattern: re.Pattern[str]
    weight: float           # contribution to risk score (0–100)
    description: str


# OWASP LLM01-aligned heuristics
_RULES: tuple[InjectionRule, ...] = (
    InjectionRule(
        name="instruction_override",
        pattern=re.compile(
            r"\b(ignore|disregard|forget|override)\b.{0,30}\b"
            r"(previous|prior|above|all)\b.{0,20}\b(instructions?|prompts?|rules?)\b",
            re.IGNORECASE,
        ),
        weight=35.0,
        description="Attempt to override prior system instructions.",
    ),
    InjectionRule(
        name="role_hijack",
        pattern=re.compile(
            r"\b(you are now|act as|pretend to be|roleplay as)\b.{0,40}"
            r"(dan|jailbroken|admin|root|developer mode|unfiltered)",
            re.IGNORECASE,
        ),
        weight=30.0,
        description="Role-hijacking / persona escape attempt.",
    ),
    InjectionRule(
        name="system_prompt_exfil",
        pattern=re.compile(
            r"\b(reveal|show|print|leak|repeat|output)\b.{0,30}"
            r"\b(system prompt|hidden prompt|initial instructions?|your rules?)\b",
            re.IGNORECASE,
        ),
        weight=25.0,
        description="Attempt to exfiltrate system prompt or hidden context.",
    ),
    InjectionRule(
        name="delimiter_injection",
        pattern=re.compile(
            r"(```|###|---|\[INST\]|<\|.*?\|>|<system>|</system>)",
            re.IGNORECASE,
        ),
        weight=10.0,
        description="Suspicious delimiter/markup that may break context boundaries.",
    ),
    InjectionRule(
        name="encoded_payload",
        pattern=re.compile(
            r"\b(base64|rot13|hex decode|decode this)\b|"
            r"(?:[A-Za-z0-9+/]{40,}={0,2})",
        ),
        weight=15.0,
        description="Encoded payload that could smuggle hidden instructions.",
    ),
    InjectionRule(
        name="tool_abuse",
        pattern=re.compile(
            r"\b(execute|run|eval|os\.system|subprocess|shell|curl|wget)\b",
            re.IGNORECASE,
        ),
        weight=20.0,
        description="Possible attempt to invoke tools / shell execution.",
    ),
)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
class PromptInjectionAgent:
    """Detects prompt-injection patterns using deterministic rules."""

    CATEGORY = "prompt_injection"

    def assess(self, prompt: str, context: str | None = None) -> AgentResult:
        haystack = f"{prompt}\n{context or ''}"
        findings: list[Finding] = []
        score = 0.0

        for rule in _RULES:
            match = rule.pattern.search(haystack)
            if match:
                score += rule.weight
                findings.append(
                    Finding(
                        category=self.CATEGORY,
                        description=rule.description,
                        evidence=match.group(0)[:200],
                        severity=self._severity_for_weight(rule.weight),
                    )
                )

        score = min(score, 100.0)
        severity = self._overall_severity(score)
        recommendations = self._recommendations(findings, score)

        return AgentResult(
            category=self.CATEGORY,
            risk_score=round(score, 2),
            severity=severity,
            findings=findings,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _severity_for_weight(weight: float) -> Severity:
        if weight >= 30:
            return Severity.HIGH
        if weight >= 15:
            return Severity.MEDIUM
        return Severity.LOW

    @staticmethod
    def _overall_severity(score: float) -> Severity:
        if score >= 60:
            return Severity.CRITICAL
        if score >= 35:
            return Severity.HIGH
        if score >= 15:
            return Severity.MEDIUM
        if score > 0:
            return Severity.LOW
        return Severity.NONE

    @staticmethod
    def _recommendations(findings: list[Finding], score: float) -> list[str]:
        if not findings:
            return ["No injection patterns detected. Continue monitoring."]

        recs = [
            "Enforce strict system-prompt isolation (use role separation).",
            "Sanitize and validate untrusted user input before LLM calls.",
            "Apply an input-side guardrail (e.g., regex + classifier).",
        ]
        if score >= 35:
            recs.append("Block or human-review this request before execution.")
        if any(f.description.startswith("Possible attempt to invoke tools") for f in findings):
            recs.append("Disable or sandbox tool/function-calling for this session.")
        if any("system prompt" in f.description.lower() for f in findings):
            recs.append("Never echo system prompt; redact in outputs.")
        return recs