"""
Streamlit UI for the AI Risk Assessment Agent.

Run with:
    streamlit run ui/streamlit_app.py
"""
import os
from typing import Any

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
RISK_ENDPOINT = f"{API_BASE_URL}/api/v1/risk/assess"
HEALTH_ENDPOINT = f"{API_BASE_URL}/api/v1/health"
REQUEST_TIMEOUT = 60

SEVERITY_COLORS = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Risk Assessment Agent",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ AI Risk Assessment Agent")
st.caption(
    "Assess prompt injection, privacy, hallucination, drift, and compliance risks "
    "across your AI systems."
)

# ---------------------------------------------------------------------------
# Sidebar — backend status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Backend Status")
    st.text(f"API: {API_BASE_URL}")

    if st.button("Check Health"):
        try:
            r = requests.get(HEALTH_ENDPOINT, timeout=5)
            if r.status_code == 200:
                st.success("Backend is healthy ✅")
                st.json(r.json())
            else:
                st.error(f"Unhealthy: HTTP {r.status_code}")
        except requests.RequestException as e:
            st.error(f"Cannot reach backend: {e}")

    st.divider()
    st.markdown("**Risk Categories Assessed**")
    st.markdown(
        "- Prompt Injection\n"
        "- Privacy\n"
        "- Hallucination\n"
        "- Model Drift\n"
        "- Compliance Gaps"
    )


# ---------------------------------------------------------------------------
# Intake form
# ---------------------------------------------------------------------------
st.subheader("📋 AI System Intake")

with st.form("risk_intake_form", clear_on_submit=False):
    col1, col2 = st.columns(2)

    with col1:
        system_name = st.text_input(
            "System Name *",
            placeholder="e.g., Customer Support Copilot",
        )
        model_used = st.text_input(
            "Model Used *",
            placeholder="e.g., gpt-4o, claude-3.5-sonnet",
        )
        deployment_env = st.selectbox(
            "Deployment Environment",
            ["development", "staging", "production"],
            index=2,
        )

    with col2:
        use_case = st.text_input(
            "Primary Use Case *",
            placeholder="e.g., Answer customer billing questions",
        )
        data_types = st.multiselect(
            "Data Types Handled",
            [
                "PII", "PHI", "Financial", "Credentials",
                "Source Code", "Internal Docs", "Public Data",
            ],
            default=["Public Data"],
        )
        compliance_frameworks = st.multiselect(
            "Compliance Requirements",
            ["GDPR", "HIPAA", "SOC2", "PCI-DSS", "EU AI Act", "ISO 27001"],
        )

    description = st.text_area(
        "System Description *",
        placeholder=(
            "Describe what this AI system does, who uses it, "
            "and how it interacts with users and data sources..."
        ),
        height=140,
    )

    submitted = st.form_submit_button(
        "🔍 Run Risk Assessment",
        use_container_width=True,
        type="primary",
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def _render_score(result: dict[str, Any]) -> None:
    score = result.get("overall_risk_score", 0)
    severity = (result.get("severity") or "unknown").lower()
    icon = SEVERITY_COLORS.get(severity, "⚪")

    c1, c2, c3 = st.columns(3)
    c1.metric("Overall Risk Score", f"{score}/100")
    c2.metric("Severity", f"{icon} {severity.upper()}")
    c3.metric("Findings", len(result.get("findings", [])))

    st.progress(min(max(score, 0), 100) / 100)


def _render_findings(findings: list[dict[str, Any]]) -> None:
    if not findings:
        st.info("No findings reported.")
        return

    for f in findings:
        sev = (f.get("severity") or "low").lower()
        icon = SEVERITY_COLORS.get(sev, "⚪")
        with st.expander(
            f"{icon} {f.get('category', 'Unknown')} — {sev.upper()}",
            expanded=(sev in {"high", "critical"}),
        ):
            st.markdown(f"**Description:** {f.get('description', '—')}")
            if f.get("evidence"):
                st.markdown(f"**Evidence:** {f['evidence']}")
            if f.get("score") is not None:
                st.caption(f"Category Score: {f['score']}/100")


def _render_recommendations(recs: list[str]) -> None:
    if not recs:
        st.info("No recommendations generated.")
        return
    for i, rec in enumerate(recs, start=1):
        st.markdown(f"**{i}.** {rec}")


# ---------------------------------------------------------------------------
# Submission handler
# ---------------------------------------------------------------------------
if submitted:
    missing = [
        label for label, value in [
            ("System Name", system_name),
            ("Model Used", model_used),
            ("Primary Use Case", use_case),
            ("System Description", description),
        ] if not value.strip()
    ]
    if missing:
        st.error(f"Please fill in required fields: {', '.join(missing)}")
        st.stop()

    payload = {
        "system_name": system_name.strip(),
        "model_used": model_used.strip(),
        "use_case": use_case.strip(),
        "description": description.strip(),
        "deployment_env": deployment_env,
        "data_types": data_types,
        "compliance_frameworks": compliance_frameworks,
    }

    with st.spinner("🤖 Analyzing risks across all categories..."):
        try:
            response = requests.post(
                RISK_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT
            )
        except requests.Timeout:
            st.error("⏱️ Request timed out. The assessment took too long.")
            st.stop()
        except requests.RequestException as e:
            st.error(f"🚫 Failed to reach backend: {e}")
            st.stop()

    if response.status_code != 200:
        st.error(f"Backend error ({response.status_code}): {response.text}")
        st.stop()

    result = response.json()
    st.success("✅ Assessment complete")

    st.divider()
    st.subheader("📊 Risk Summary")
    _render_score(result)

    st.divider()
    st.subheader("🔍 Findings")
    _render_findings(result.get("findings", []))

    st.divider()
    st.subheader("💡 Recommendations")
    _render_recommendations(result.get("recommendations", []))

    with st.expander("🧾 Raw Response (debug)"):
        st.json(result)