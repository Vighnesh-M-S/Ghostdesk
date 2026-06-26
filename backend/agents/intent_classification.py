import json
import logging
import os
from backend.models import GhostDeskState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

SUPPORTED_INTENTS = [
    "REFUND_REQUEST",
    "PAYMENT_ISSUE",
    "TECHNICAL_ISSUE",
    "ACCOUNT_ACCESS",
    "FEATURE_REQUEST",
    "COMPLAINT",
    "GENERAL_QUERY",
]

_SYSTEM = """You are an expert customer support AI that classifies customer intent.

Classify the provided email into exactly one of these intents:
- REFUND_REQUEST: Customer wants a refund for a purchase or service
- PAYMENT_ISSUE: Problems with payment processing, billing, or charges
- TECHNICAL_ISSUE: Technical problems, bugs, or system not working
- ACCOUNT_ACCESS: Login issues, account locked, or password reset
- FEATURE_REQUEST: Requesting new features or improvements
- COMPLAINT: General complaints about service or experience
- GENERAL_QUERY: General questions or information requests

Respond with ONLY a valid JSON object — no markdown, no explanation:
{
    "intent": "INTENT_NAME",
    "confidence": 0.95,
    "reasoning": "Brief explanation"
}"""


def _parse_json(content: str) -> dict:
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def intent_classification_node(state: GhostDeskState) -> dict:
    """Classify customer intent from the redacted email."""
    text = state.get("redacted_email") or state.get("email_text", "")
    errors = list(state.get("processing_errors", []))

    try:
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.1,
        )
        response = llm.invoke([SystemMessage(content=_SYSTEM), HumanMessage(content=text)])
        result = _parse_json(response.content)

        intent = result.get("intent", "GENERAL_QUERY").upper()
        if intent not in SUPPORTED_INTENTS:
            intent = "GENERAL_QUERY"
        confidence = min(max(float(result.get("confidence", 0.5)), 0.0), 1.0)

        return {"intent": intent, "intent_confidence": confidence, "processing_errors": errors}

    except Exception as exc:
        logger.error("Intent classification error: %s", exc)
        errors.append(f"Intent classification failed: {exc}")
        return {"intent": "GENERAL_QUERY", "intent_confidence": 0.5, "processing_errors": errors}
