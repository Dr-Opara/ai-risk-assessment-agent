"""
Privacy Risk Agent
------------------
Detects PII, PHI, secrets, and sensitive identifiers using deterministic
regex heuristics. Designed to be replaced/augmented later with an LLM
or Presidio-based detector.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.risk import AgentResult, Finding, Severity


@dataclass(frozen=True)
class PrivacyRule:
    name: str
    pattern: re.Pattern[str]
    weight: float
    description: str
    pii_class: str  # e.g., "PII", "PHI", "SECRET", "FINANCIAL"


_RULES: tuple[PrivacyRule, ...] = (
    PrivacyRule(
        name="email",
        pattern=re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
        weight=15.0,
        description="Email address detected.",
        pii_class="PII",
    ),
    PrivacyRule(
        name="phone",
        pattern=re.compile(
            r"(?:(?:\+?\d{1,3}[\s\-.])?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})\b"
        ),
        weight=15.0,
        description="Phone number detected.",
        pii_class="PII",
    ),
    PrivacyRule(
        name="ssn_us",
        pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        weight=35.0,
        description="US Social Security Number detected.",
        pii_class="PII",
    ),
    PrivacyRule(
        name="credit_card",
        pattern=re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
        weight=35.0,
        description="Possible credit card number detected.",
        pii_class="FINANCIAL",
    ),
    PrivacyRule(
        name="iban",
        pattern=re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"),
        weight=25.0,
        description="IBAN bank account identifier detected.",
        pii_class="FINANCIAL",
    ),
    PrivacyRule(
        name="ip_address",
        pattern=re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        weight=10.0,
        description="IP address detected.",
        pii_class="PII",
    ),
    PrivacyRule(
        name="api_key_generic",
        pattern=re.compile(r"\b(sk|pk|api|secret)[_\-][A-Za-z0-9]{16,}\b", re.IGNORECASE),
        weight=40.0,
        description="API key / secret token pattern detected.",
        pii_class="SECRET",
    ),
    PrivacyRule(
        name="aws_access_key",
        pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        weight=45.0,
        description="AWS access key detected.",
        pii_class="SECRET",
    ),
    PrivacyRule(
        name="jwt",
        pattern=re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
        weight=30.0,
        description="JWT token detected.",
        pii_class="SECRET",
    ),
    PrivacyRule(
        name="date_of_birth",
        pattern=re.compile(
            r"\b(?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b"
        ),
        weight=15.0,
        description="Date of birth pattern detected.",
        pii_class="PII",
    ),
    PrivacyRule(
        name="medical_terms",
        pattern=re.compile(
            r"\b(diagnosis|prescription|patient id|mrn|icd-10|hipaa)\b",
            re.IGNORECASE,
        ),
        weight=20.0,
        description="Medical / PHI terminology detected.",
        pii_class="PHI",
    ),
)


class PrivacyAgent:
    """Deterministic PII / secret detector."""

    CATEGORY = "privacy"

    def assess(self, prompt: str, context: str | None = None) -> AgentResult:
        haystack = f"{prompt}\n{context or ''}"
        findings: list[Finding] = []
        score = 0.0
        pii_classes_seen: set[str] = set()

        for rule in _RULES:
            for match in rule.pattern.finditer(haystack):
                score += rule.weight
                pii_classes_seen.add(rule.pii_class)
                findings.append(
                    Finding(
                        category=self.CATEGORY,
                        description=f"[{rule.pii_class}] {rule.description}",
                        evidence=self._redact(match.group(0)),
                        severity=self._severity_for_weight(rule.weight),
                    )
                )

        score = min(score, 100.0)
        severity = self._overall_severity(score)
        recommendations = self._recommendations(pii_classes_seen, score)

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
    def _redact(value: str) -> str:
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"

    @staticmethod
    def _severity_for_weight(weight: float) -> Severity:
        if weight >= 35:
            return Severity.HIGH
        if weight >= 20:
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
    def _recommendations(classes: set[str], score: float) -> list[str]:
        if not classes:
            return ["No sensitive data patterns detected."]

        recs: list[str] = [
            "Apply PII redaction before sending data to the LLM.",
            "Log sanitized payloads only; never log raw prompts.",
        ]
        if "SECRET" in classes:
            recs.append("Rotate exposed credentials immediately and revoke the token.")
            recs.append("Add a pre-commit / pre-prompt secret scanner (e.g., gitleaks).")
        if "PHI" in classes:
            recs.append("Ensure HIPAA-compliant data handling and BAA coverage.")
        if "FINANCIAL" in classes:
            recs.append("Apply PCI-DSS controls; do not store cardholder data in prompts.")
        if score >= 60:
            recs.append("Block this request and escalate to a data-protection reviewer.")
        return recs