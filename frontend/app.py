import os
import json
from pathlib import Path

import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

# Streamlit Cloud secrets take priority, then env var, then local default
try:
    API_URL = st.secrets.get("GHOSTDESK_API_URL", os.getenv("GHOSTDESK_API_URL", "http://localhost:8000"))
except Exception:
    API_URL = os.getenv("GHOSTDESK_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="GhostDesk — AI Support Employee",
    page_icon="👻",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Base */
    [data-testid="stAppViewContainer"] { background: #0f1117; }
    [data-testid="stSidebar"] { background: #161b27; border-right: 1px solid #1f2937; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* Cards */
    .gd-card {
        background: #161b27;
        border: 1px solid #1f2937;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    .gd-card-title {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #6b7280;
        margin-bottom: 10px;
    }
    .gd-value { font-size: 1.6rem; font-weight: 700; color: #f9fafb; }
    .gd-sub   { font-size: 0.85rem; color: #9ca3af; margin-top: 4px; }

    /* Badges */
    .badge {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        border-radius: 6px;
        padding: 3px 10px;
    }
    .badge-green  { background: #064e3b; color: #34d399; border: 1px solid #065f46; }
    .badge-yellow { background: #451a03; color: #fbbf24; border: 1px solid #78350f; }
    .badge-red    { background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
    .badge-blue   { background: #1e3a5f; color: #93c5fd; border: 1px solid #1e40af; }
    .badge-gray   { background: #1f2937; color: #9ca3af; border: 1px solid #374151; }

    /* Alert boxes */
    .alert-red    { background: #1c0a0a; border: 1px solid #991b1b; border-radius: 10px; padding: 14px 18px; color: #f87171; }
    .alert-yellow { background: #1c1000; border: 1px solid #92400e; border-radius: 10px; padding: 14px 18px; color: #fbbf24; }
    .alert-green  { background: #021c0f; border: 1px solid #065f46; border-radius: 10px; padding: 14px 18px; color: #34d399; }

    /* Risk bar */
    .risk-bar-bg { background: #1f2937; border-radius: 6px; height: 10px; overflow: hidden; margin-top: 6px; }
    .risk-bar-fill { height: 10px; border-radius: 6px; transition: width 0.5s ease; }

    /* Redacted text */
    .redacted-block {
        background: #0d1117;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 14px 18px;
        font-family: 'Courier New', monospace;
        font-size: 0.83rem;
        color: #d1d5db;
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 220px;
        overflow-y: auto;
    }
    .pii-tag { background: #1e3a5f; color: #93c5fd; border-radius: 4px; padding: 1px 5px; font-weight: 700; }

    /* Sidebar nav radio */
    [data-testid="stRadio"] label { font-size: 0.95rem !important; }

    /* Hide default Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }

    /* Divider */
    hr { border-color: #1f2937; }

    /* Flag list */
    .flag-item { color: #f87171; font-size: 0.88rem; margin: 4px 0; }
    .reason-item { color: #fbbf24; font-size: 0.88rem; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 👻 GhostDesk")
    st.markdown("<span style='color:#6b7280;font-size:0.82rem'>Privacy-first AI Support Employee</span>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio(
        "nav",
        ["🔍  Process Request", "📊  Analytics Dashboard"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.75rem;color:#4b5563'>"
        "Powered by Gemini · LangGraph<br>PII protected by Presidio"
        "</div>",
        unsafe_allow_html=True,
    )
    with st.expander("⚙️  Settings", expanded=False):
        api_url = st.text_input("API URL", value=API_URL)
        if api_url != API_URL:
            API_URL = api_url

# ─── Helpers ──────────────────────────────────────────────────────────────────

SAMPLE_EMAILS = {
    "Refund Request": Path("sample_data/test_emails/refund_request.txt"),
    "Technical Issue": Path("sample_data/test_emails/technical_issue.txt"),
    "Fraud Scenario": Path("sample_data/test_emails/fraud_scenario.txt"),
}

ACTION_LABELS = {
    "APPROVE_REFUND": ("✅ Approve Refund", "badge-green"),
    "CREATE_JIRA": ("🎫 Create Jira Ticket", "badge-blue"),
    "ESCALATE_FINANCE": ("💰 Escalate Finance", "badge-yellow"),
    "ESCALATE_SUPPORT": ("🚨 Escalate to Human", "badge-red"),
    "REQUEST_MORE_INFORMATION": ("📋 Request More Info", "badge-yellow"),
    "CLOSE_REQUEST": ("✔️ Close Request", "badge-gray"),
}

VERIFICATION_LABELS = {
    "MATCH": ("✅ VERIFIED — Claims match documents", "badge-green"),
    "PARTIAL_MATCH": ("⚠️ PARTIAL MATCH — Some claims verified", "badge-yellow"),
    "MISMATCH": ("❌ MISMATCH — Claims contradict evidence", "badge-red"),
    "UNVERIFIABLE": ("❓ UNVERIFIABLE — Cannot confirm from documents", "badge-gray"),
    "NO_ATTACHMENTS": ("📎 NO ATTACHMENTS — Nothing to verify", "badge-gray"),
}

INTENT_ICONS = {
    "REFUND_REQUEST": "💳",
    "PAYMENT_ISSUE": "💰",
    "TECHNICAL_ISSUE": "🔧",
    "ACCOUNT_ACCESS": "🔐",
    "FEATURE_REQUEST": "💡",
    "COMPLAINT": "⚠️",
    "GENERAL_QUERY": "❓",
}


def badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{text}</span>'


def risk_color(score: float) -> tuple[str, str]:
    if score < 0.3:
        return "#10b981", "badge-green"
    elif score < 0.7:
        return "#f59e0b", "badge-yellow"
    return "#ef4444", "badge-red"


def risk_label(score: float) -> str:
    if score < 0.3:
        return "LOW RISK"
    elif score < 0.7:
        return "MEDIUM RISK"
    return "HIGH RISK"


def conf_color(conf: float) -> str:
    if conf >= 0.8:
        return "#10b981"
    elif conf >= 0.6:
        return "#f59e0b"
    return "#ef4444"


def highlight_pii(text: str) -> str:
    """Wrap redaction tags in styled spans for display."""
    import re
    tags = ["[NAME]", "[EMAIL]", "[PHONE_NUMBER]", "[CREDIT_CARD]", "[ADDRESS]",
            "[ACCOUNT_NUMBER]", "[SSN]", "[PAN]", "[AADHAAR]", "[REDACTED]"]
    for tag in tags:
        text = text.replace(tag, f'<span class="pii-tag">{tag}</span>')
    return text


def call_api(email_text: str, attachments=None) -> dict:
    files = []
    if attachments:
        for f in attachments:
            f.seek(0)
            files.append(("attachments", (f.name, f.read(), f.type or "application/octet-stream")))
    data = {"email_text": email_text}
    resp = requests.post(f"{API_URL}/process", data=data, files=files if files else None, timeout=120)
    resp.raise_for_status()
    return resp.json()


def load_analytics() -> dict:
    resp = requests.get(f"{API_URL}/analytics", timeout=15)
    resp.raise_for_status()
    return resp.json()


# ─── Page 1: Process Request ──────────────────────────────────────────────────

def render_process_page():
    st.markdown("## 🔍 Process Support Request")
    st.markdown("<span style='color:#6b7280'>Upload a support email and any attachments to run the full AI analysis pipeline.</span>", unsafe_allow_html=True)
    st.markdown("---")

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### 📧 Email Input")

        # Quick-load sample emails
        sample_choice = st.selectbox(
            "Load a sample email (optional)",
            ["— select —"] + list(SAMPLE_EMAILS.keys()),
        )
        prefill = ""
        if sample_choice != "— select —":
            path = SAMPLE_EMAILS[sample_choice]
            if path.exists():
                prefill = path.read_text()

        email_text = st.text_area(
            "Email content",
            value=prefill,
            height=300,
            placeholder="Paste the customer's support email here…",
            label_visibility="collapsed",
        )

        st.markdown("### 📎 Attachments")
        uploaded_files = st.file_uploader(
            "Upload attachments",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded_files:
            for uf in uploaded_files:
                st.caption(f"📄 {uf.name} ({uf.size / 1024:.1f} KB)")

        st.markdown("")
        process_btn = st.button("⚡ Process Email", type="primary", use_container_width=True)

    with col_right:
        if process_btn:
            if not email_text.strip():
                st.error("Please enter email content before processing.")
                return

            with st.spinner("🤖 Running GhostDesk AI pipeline…"):
                try:
                    result = call_api(email_text, uploaded_files if uploaded_files else None)
                except requests.ConnectionError:
                    st.error("Cannot connect to GhostDesk API. Make sure the backend is running:\n```\nuvicorn backend.main:app --reload\n```")
                    return
                except Exception as exc:
                    st.error(f"API error: {exc}")
                    return

            if not result.get("success"):
                st.error(f"Processing failed: {result.get('error', 'Unknown error')}")
                return

            data = result["data"]
            st.session_state["last_result"] = data
            st.success("✅ Processing complete!")

        data = st.session_state.get("last_result")
        if not data:
            st.markdown(
                "<div class='gd-card' style='text-align:center;padding:40px'>"
                "<div style='font-size:3rem'>👻</div>"
                "<div style='color:#6b7280;margin-top:12px'>Results will appear here after processing.</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            return

        _render_results(data)


def _render_results(data: dict):
    intent = data.get("intent", "—")
    confidence = data.get("intent_confidence", 0.0)
    risk_score = data.get("risk_score", 0.0)
    risk_flags = data.get("risk_flags", [])
    verification = data.get("verification_result", "—")
    action = data.get("recommended_action", "—")
    summary = data.get("resolution_summary", "")
    requires_human = data.get("requires_human_review", False)
    human_reasons = data.get("human_review_reasons", [])
    redacted_email = data.get("redacted_email", "")
    attachment_summary = data.get("attachment_summary", "")
    errors = data.get("processing_errors", [])

    # ── Human Review Alert ────────────────────────────────────────────
    if requires_human:
        reasons_html = "".join(f"<div class='reason-item'>⚠ {r}</div>" for r in human_reasons)
        st.markdown(
            f"<div class='alert-red'><b>🚨 HUMAN REVIEW REQUIRED</b>{reasons_html}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='alert-green'>✅ <b>AUTO-APPROVED</b> — No human review required</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Intent + Confidence ───────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        icon = INTENT_ICONS.get(intent, "❓")
        st.markdown(
            f"<div class='gd-card'>"
            f"<div class='gd-card-title'>Detected Intent</div>"
            f"<div class='gd-value'>{icon} {intent.replace('_', ' ')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col2:
        conf_pct = int(confidence * 100)
        c_color = conf_color(confidence)
        st.markdown(
            f"<div class='gd-card'>"
            f"<div class='gd-card-title'>Confidence</div>"
            f"<div class='gd-value' style='color:{c_color}'>{conf_pct}%</div>"
            f"<div class='risk-bar-bg'><div class='risk-bar-fill' style='width:{conf_pct}%;background:{c_color}'></div></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Recommended Action ────────────────────────────────────────────
    action_label, action_cls = ACTION_LABELS.get(action, (action, "badge-gray"))
    st.markdown(
        f"<div class='gd-card'>"
        f"<div class='gd-card-title'>Recommended Action</div>"
        f"<div style='margin-bottom:10px'>{badge(action_label, action_cls)}</div>"
        f"<div class='gd-sub'>{summary}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Verification + Risk ───────────────────────────────────────────
    col3, col4 = st.columns(2)
    with col3:
        ver_label, ver_cls = VERIFICATION_LABELS.get(verification, (verification, "badge-gray"))
        st.markdown(
            f"<div class='gd-card'>"
            f"<div class='gd-card-title'>Claim Verification</div>"
            f"<div style='margin-top:8px'>{badge(ver_label, ver_cls)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col4:
        r_color, r_cls = risk_color(risk_score)
        r_label = risk_label(risk_score)
        r_pct = int(risk_score * 100)
        st.markdown(
            f"<div class='gd-card'>"
            f"<div class='gd-card-title'>Risk Score</div>"
            f"<div class='gd-value' style='color:{r_color}'>{r_pct}%</div>"
            f"<div class='risk-bar-bg'><div class='risk-bar-fill' style='width:{r_pct}%;background:{r_color}'></div></div>"
            f"<div style='margin-top:8px'>{badge(r_label, r_cls)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Risk Flags ────────────────────────────────────────────────────
    if risk_flags:
        flags_html = "".join(f"<div class='flag-item'>⚠ {f}</div>" for f in risk_flags)
        st.markdown(
            f"<div class='gd-card'>"
            f"<div class='gd-card-title'>Risk Flags</div>"
            f"{flags_html}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Attachment Summary ────────────────────────────────────────────
    if attachment_summary and attachment_summary != "No attachments provided.":
        st.markdown(
            f"<div class='gd-card'>"
            f"<div class='gd-card-title'>📎 Attachment Analysis</div>"
            f"<div class='gd-sub'>{attachment_summary}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Redacted Email ────────────────────────────────────────────────
    with st.expander("🔏 View Redacted Email (PII removed)", expanded=False):
        highlighted = highlight_pii(redacted_email)
        st.markdown(f"<div class='redacted-block'>{highlighted}</div>", unsafe_allow_html=True)

    # ── Processing Errors ─────────────────────────────────────────────
    if errors:
        with st.expander("⚠️ Processing Warnings", expanded=False):
            for e in errors:
                st.caption(f"• {e}")


# ─── Page 2: Analytics ────────────────────────────────────────────────────────

def render_analytics_page():
    st.markdown("## 📊 Analytics Dashboard")
    st.markdown("<span style='color:#6b7280'>Real-time metrics from all processed support requests.</span>", unsafe_allow_html=True)
    st.markdown("---")

    try:
        stats = load_analytics()
    except requests.ConnectionError:
        st.error("Cannot reach the API. Start the backend with: `uvicorn backend.main:app --reload`")
        return
    except Exception as exc:
        st.error(f"Failed to load analytics: {exc}")
        return

    total = stats.get("total_processed", 0)

    # ── KPI Cards ─────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    kpis = [
        (c1, "Emails Processed", str(total), "All time"),
        (c2, "Automation Rate", f"{stats.get('automation_rate', 0):.1f}%", "No human needed"),
        (c3, "Human Review Rate", f"{stats.get('human_review_rate', 0):.1f}%", "Escalated cases"),
        (c4, "Avg Confidence", f"{stats.get('avg_confidence', 0):.1f}%", "Intent accuracy"),
    ]
    for col, title, value, sub in kpis:
        col.markdown(
            f"<div class='gd-card'><div class='gd-card-title'>{title}</div>"
            f"<div class='gd-value'>{value}</div><div class='gd-sub'>{sub}</div></div>",
            unsafe_allow_html=True,
        )

    if total == 0:
        st.markdown(
            "<div class='gd-card' style='text-align:center;padding:40px;margin-top:16px'>"
            "<div style='font-size:2rem'>📭</div>"
            "<div style='color:#6b7280;margin-top:8px'>No emails processed yet. Use the Process Request page to get started.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown("")
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        # Intent Distribution
        intent_data = stats.get("intent_distribution", {})
        if intent_data:
            fig = px.pie(
                names=list(intent_data.keys()),
                values=list(intent_data.values()),
                title="Intent Distribution",
                color_discrete_sequence=px.colors.qualitative.Set3,
                hole=0.4,
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#d1d5db",
                title_font_color="#f9fafb",
                legend_font_color="#d1d5db",
                margin=dict(t=40, b=10, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Risk Distribution
        risk_data = stats.get("risk_distribution", {})
        if risk_data:
            order = ["Low", "Medium", "High"]
            risk_ordered = {k: risk_data.get(k, 0) for k in order if k in risk_data}
            risk_colors = {"Low": "#10b981", "Medium": "#f59e0b", "High": "#ef4444"}
            fig2 = px.bar(
                x=list(risk_ordered.keys()),
                y=list(risk_ordered.values()),
                title="Risk Distribution",
                color=list(risk_ordered.keys()),
                color_discrete_map=risk_colors,
                labels={"x": "Risk Level", "y": "Count"},
            )
            fig2.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#d1d5db",
                title_font_color="#f9fafb",
                showlegend=False,
                margin=dict(t=40, b=10, l=10, r=10),
            )
            fig2.update_xaxes(showgrid=False)
            fig2.update_yaxes(showgrid=True, gridcolor="#1f2937")
            st.plotly_chart(fig2, use_container_width=True)

    with col_right:
        # Action Distribution
        action_data = stats.get("action_distribution", {})
        if action_data:
            fig3 = px.bar(
                x=list(action_data.values()),
                y=[a.replace("_", " ") for a in action_data.keys()],
                orientation="h",
                title="Recommended Actions",
                color_discrete_sequence=["#3b82f6"],
                labels={"x": "Count", "y": "Action"},
            )
            fig3.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#d1d5db",
                title_font_color="#f9fafb",
                margin=dict(t=40, b=10, l=10, r=10),
            )
            fig3.update_xaxes(showgrid=True, gridcolor="#1f2937")
            fig3.update_yaxes(showgrid=False)
            st.plotly_chart(fig3, use_container_width=True)

        # Human vs Automated
        fig4 = go.Figure(data=[go.Pie(
            labels=["Automated", "Human Review"],
            values=[stats.get("automated", 0), stats.get("human_review", 0)],
            hole=0.5,
            marker_colors=["#10b981", "#ef4444"],
        )])
        fig4.update_layout(
            title="Automation vs Human Review",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#d1d5db",
            title_font_color="#f9fafb",
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig4, use_container_width=True)

    # ── Recent History Table ───────────────────────────────────────────
    st.markdown("### 🕒 Recent Requests")
    recent = stats.get("recent", [])
    if recent:
        import pandas as pd
        df = pd.DataFrame(recent)
        df["requires_human_review"] = df["requires_human_review"].map({0: "No", 1: "Yes", False: "No", True: "Yes"})
        df["confidence"] = (df["confidence"] * 100).round(1).astype(str) + "%"
        df["risk_score"] = (df["risk_score"] * 100).round(1).astype(str) + "%"
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%b %d, %Y %H:%M")
        df = df.rename(columns={
            "created_at": "Time",
            "intent": "Intent",
            "confidence": "Confidence",
            "risk_score": "Risk",
            "recommended_action": "Action",
            "requires_human_review": "Human Review",
            "verification_result": "Verification",
        })
        st.dataframe(df[["Time", "Intent", "Confidence", "Risk", "Action", "Verification", "Human Review"]], use_container_width=True)
    else:
        st.caption("No recent requests.")


# ─── Router ───────────────────────────────────────────────────────────────────
if page == "🔍  Process Request":
    render_process_page()
else:
    render_analytics_page()
