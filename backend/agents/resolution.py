import json
import logging
import os
from backend.models import GhostDeskState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = [
    "APPROVE_REFUND",
    "CREATE_JIRA",
    "ESCALATE_FINANCE",
    "ESCALATE_SUPPORT",
    "REQUEST_MORE_INFORMATION",
    "CLOSE_REQUEST",
]

_SYSTEM = """You are a senior customer support resolution specialist.

Recommend the most appropriate action for this support request:
- APPROVE_REFUND: Approve refund — use when claims are verified, risk is low
- CREATE_JIRA: Create technical ticket — use for bugs, outages, technical issues
- ESCALATE_FINANCE: Escalate to finance — use for complex billing/payment disputes
- ESCALATE_SUPPORT: Escalate to human senior agent — use for high-risk or ambiguous cases
- REQUEST_MORE_INFORMATION: Ask customer for more details or documentation
- CLOSE_REQUEST: Close — resolved, duplicate, or no action needed

Respond with ONLY a valid JSON object:
{
    "recommended_action": "ACTION_NAME",
    "confidence": 0.9,
    "reasoning": "Why this action was chosen",
    "summary": "Customer-friendly one-paragraph resolution summary"
}"""


def _parse_json(content: str) -> dict:
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def resolution_node(state: GhostDeskState) -> dict:
    """Recommend the best action to resolve the support request."""
    redacted_email = state.get("redacted_email") or state.get("email_text", "")
    intent = state.get("intent", "GENERAL_QUERY")
    confidence = state.get("intent_confidence", 0.5)
    attachment_summary = state.get("attachment_summary", "")
    verification_result = state.get("verification_result", "")
    risk_score = state.get("risk_score", 0.5)
    risk_flags = state.get("risk_flags", [])
    errors = list(state.get("processing_errors", []))

    try:
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.2,
        )

        context = (
            f"INTENT: {intent} | CONFIDENCE: {confidence:.0%}\n"
            f"VERIFICATION: {verification_result}\n"
            f"RISK SCORE: {risk_score:.2f} | RISK FLAGS: {', '.join(risk_flags) or 'None'}\n\n"
            f"CUSTOMER EMAIL:\n{redacted_email}\n\n"
            f"DOCUMENT EVIDENCE:\n{attachment_summary}"
        )
        response = llm.invoke([SystemMessage(content=_SYSTEM), HumanMessage(content=context)])
        result = _parse_json(response.content)

        action = result.get("recommended_action", "ESCALATE_SUPPORT").upper()
        if action not in SUPPORTED_ACTIONS:
            action = "ESCALATE_SUPPORT"

        # Safety override: very high risk must escalate
        if risk_score >= 0.85 and action not in ("ESCALATE_SUPPORT", "ESCALATE_FINANCE"):
            action = "ESCALATE_SUPPORT"

        return {
            "recommended_action": action,
            "resolution_summary": result.get("summary") or result.get("reasoning", ""),
            "processing_errors": errors,
        }

    except Exception as exc:
        logger.error("Resolution error: %s", exc)
        errors.append(f"Resolution failed: {exc}")
        return {
            "recommended_action": "ESCALATE_SUPPORT",
            "resolution_summary": "Unable to generate automated resolution. Escalating to human support.",
            "processing_errors": errors,
        }
