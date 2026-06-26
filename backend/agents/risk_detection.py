import json
import logging
import os
from backend.models import GhostDeskState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

_SYSTEM = """You are a fraud and risk detection expert for customer support.

Analyze the request for risks, inconsistencies, and suspicious patterns. Consider:
- Amount mismatches between claims and evidence
- Missing documentation for high-value claims
- Unusual urgency or threatening language
- Conflicting information across sources
- Requests for unusually large sums
- Social engineering tactics

Respond with ONLY a valid JSON object:
{
    "risk_score": 0.2,
    "risk_level": "LOW|MEDIUM|HIGH",
    "risk_flags": ["specific risk identified"],
    "reasoning": "Concise explanation"
}

risk_score: 0.0 (no risk) to 1.0 (critical risk)"""


def _parse_json(content: str) -> dict:
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def risk_detection_node(state: GhostDeskState) -> dict:
    """Detect risks and suspicious patterns."""
    redacted_email = state.get("redacted_email") or state.get("email_text", "")
    intent = state.get("intent", "GENERAL_QUERY")
    confidence = state.get("intent_confidence", 0.5)
    attachment_summary = state.get("attachment_summary", "")
    verification_result = state.get("verification_result", "")
    errors = list(state.get("processing_errors", []))

    try:
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.1,
        )

        context = (
            f"INTENT: {intent} (confidence: {confidence:.0%})\n\n"
            f"REDACTED EMAIL:\n{redacted_email}\n\n"
            f"ATTACHMENT ANALYSIS:\n{attachment_summary}\n\n"
            f"VERIFICATION RESULT: {verification_result}"
        )
        response = llm.invoke([SystemMessage(content=_SYSTEM), HumanMessage(content=context)])
        result = _parse_json(response.content)

        risk_score = min(max(float(result.get("risk_score", 0.2)), 0.0), 1.0)
        risk_flags: list = result.get("risk_flags", [])

        # Automatic escalations based on other node outcomes
        if verification_result == "MISMATCH" and "Amount or claim mismatch with attached documents" not in risk_flags:
            risk_flags.append("Amount or claim mismatch with attached documents")
            risk_score = max(risk_score, 0.75)

        if confidence < 0.6:
            risk_flags.append("Low intent classification confidence")

        return {"risk_score": risk_score, "risk_flags": risk_flags, "processing_errors": errors}

    except Exception as exc:
        logger.error("Risk detection error: %s", exc)
        errors.append(f"Risk detection failed: {exc}")
        return {"risk_score": 0.5, "risk_flags": ["Risk assessment unavailable"], "processing_errors": errors}
