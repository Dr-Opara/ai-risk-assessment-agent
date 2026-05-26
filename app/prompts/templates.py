"""
LangChain prompt templates for AI Risk Assessment.

Each template is designed for a specific risk dimension:
- Prompt injection
- Privacy
- Hallucination
- Model drift
- Compliance

Templates enforce:
1. Strict JSON output (parseable by Pydantic)
2. Bounded score range (0-100)
3. Evidence-based reasoning
4. No hallucinated regulations
"""

from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate


# ---------------------------------------------------------------------------
# SYSTEM ROLE (shared across all risk analyzers)
# ---------------------------------------------------------------------------
SYSTEM_ROLE = """You are an expert AI Risk Assessor working for an enterprise governance team.
Your job is to evaluate AI systems against a specific risk dimension.

RULES:
1. Respond ONLY with valid JSON. No prose, no markdown fences.
2. Scores must be integers between 0 and 100 (0 = no risk, 100 = critical).
3. Base your reasoning on the provided system description ONLY.
4. Do NOT invent facts, regulations, or capabilities not stated in the input.
5. If information is insufficient, reflect that with higher uncertainty and lower confidence.
6. Keep 'rationale' under 80 words. Keep each 'finding' under 25 words.

OUTPUT SCHEMA:
{{
  "score": <int 0-100>,
  "severity": "<low|medium|high|critical>",
  "confidence": <float 0.0-1.0>,
  "findings": ["<short finding>", "..."],
  "recommendations": ["<short recommendation>", "..."],
  "rationale": "<concise explanation>"
}}
"""


# ---------------------------------------------------------------------------
# Risk-specific human prompts
# ---------------------------------------------------------------------------

PROMPT_INJECTION_TEMPLATE = """Assess PROMPT INJECTION risk for this AI system.

Consider:
- Does it accept untrusted user input directly into prompts?
- Are there guardrails (input validation, output filtering, system prompt isolation)?
- Does it use tools/function-calling that could be hijacked?
- Is there RAG over untrusted sources (indirect injection)?

AI SYSTEM DESCRIPTION:
---
{system_description}
---

Return JSON only."""


PRIVACY_TEMPLATE = """Assess PRIVACY risk for this AI system.

Consider:
- Does it process PII, PHI, financial, or biometric data?
- Are inputs/outputs logged? Where? For how long?
- Is data used to train models?
- Are there data residency or cross-border concerns?
- Is consent/purpose limitation documented?

AI SYSTEM DESCRIPTION:
---
{system_description}
---

Return JSON only."""


HALLUCINATION_TEMPLATE = """Assess HALLUCINATION risk for this AI system.

Consider:
- Is output grounded (RAG, citations, retrieval)?
- Is it used in high-stakes domains (medical, legal, financial)?
- Are there factuality checks, evals, or human-in-the-loop review?
- Does the model generate freeform text vs. structured/constrained output?

AI SYSTEM DESCRIPTION:
---
{system_description}
---

Return JSON only."""


MODEL_DRIFT_TEMPLATE = """Assess MODEL DRIFT risk for this AI system.

Consider:
- Is performance monitored over time (accuracy, latency, output distribution)?
- Are there scheduled retraining/evaluation cycles?
- Does the input distribution change (seasonality, user behavior)?
- Are there alerting mechanisms for degradation?
- Vendor model updates without notice?

AI SYSTEM DESCRIPTION:
---
{system_description}
---

Return JSON only."""


COMPLIANCE_TEMPLATE = """Assess COMPLIANCE GAP risk for this AI system.

Consider ONLY frameworks explicitly relevant to the described system, such as:
- EU AI Act, GDPR, HIPAA, SOC 2, ISO 42001, NIST AI RMF, PCI-DSS.

Evaluate:
- Documented risk assessments, model cards, data sheets?
- Audit logging and traceability?
- Human oversight and contestability?
- Role-based access control?
- Incident response plan for AI failures?

Do NOT cite regulations that don't apply to the described domain.

AI SYSTEM DESCRIPTION:
---
{system_description}
---

Return JSON only."""


# ---------------------------------------------------------------------------
# Template registry (used by the service layer)
# ---------------------------------------------------------------------------
def _build_chat_template(human_template: str) -> ChatPromptTemplate:
    """Wrap a human template with the shared system role."""
    return ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SYSTEM_ROLE),
        HumanMessagePromptTemplate.from_template(human_template),
    ])


RISK_PROMPTS: dict[str, ChatPromptTemplate] = {
    "prompt_injection": _build_chat_template(PROMPT_INJECTION_TEMPLATE),
    "privacy":          _build_chat_template(PRIVACY_TEMPLATE),
    "hallucination":    _build_chat_template(HALLUCINATION_TEMPLATE),
    "model_drift":      _build_chat_template(MODEL_DRIFT_TEMPLATE),
    "compliance":       _build_chat_template(COMPLIANCE_TEMPLATE),
}


def get_prompt(risk_dimension: str) -> ChatPromptTemplate:
    """Fetch a prompt template by risk dimension name."""
    if risk_dimension not in RISK_PROMPTS:
        raise KeyError(
            f"Unknown risk dimension: '{risk_dimension}'. "
            f"Available: {list(RISK_PROMPTS.keys())}"
        )
    return RISK_PROMPTS[risk_dimension]