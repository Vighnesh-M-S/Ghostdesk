import json
import logging
import os
from backend.models import GhostDeskState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

VALID_RESULTS = {"MATCH", "MISMATCH", "PARTIAL_MATCH", "UNVERIFIABLE", "NO_ATTACHMENTS"}

_SYSTEM = """You are a claim verification expert for customer support.

Compare the claims made in the customer's email against the evidence found in attached documents.

Respond with ONLY a valid JSON object:
{
    "result": "MATCH|MISMATCH|PARTIAL_MATCH|UNVERIFIABLE",
    "confidence": 0.9,
    "matched_claims": ["claims confirmed by documents"],
    "mismatched_claims": ["claims that contradict document evidence"],
    "unverifiable_claims": ["claims that cannot be checked from documents"],
    "reasoning": "Concise explanation"
}"""


def _parse_json(content: str) -> dict:
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def verification_node(state: GhostDeskState) -> dict:
    """Verify email claims against attachment evidence."""
    redacted_email = state.get("redacted_email") or state.get("email_text", "")
    attachment_summary = state.get("attachment_summary", "")
    attachments = state.get("attachments", [])
    errors = list(state.get("processing_errors", []))

    if not attachments or attachment_summary == "No attachments provided.":
        return {"verification_result": "NO_ATTACHMENTS", "processing_errors": errors}

    try:
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.1,
        )

        evidence_parts = []
        for att in attachments:
            analysis = att.get("analysis", {})
            if analysis:
                evidence_parts.append(f"File: {att.get('filename', 'unknown')}\n{json.dumps(analysis, indent=2)}")
        evidence_text = "\n\n".join(evidence_parts) if evidence_parts else attachment_summary

        context = f"CUSTOMER EMAIL:\n{redacted_email}\n\nDOCUMENT EVIDENCE:\n{evidence_text}"
        response = llm.invoke([SystemMessage(content=_SYSTEM), HumanMessage(content=context)])
        result = _parse_json(response.content)

        status = result.get("result", "UNVERIFIABLE").upper()
        if status not in VALID_RESULTS:
            status = "UNVERIFIABLE"

        return {"verification_result": status, "processing_errors": errors}

    except Exception as exc:
        logger.error("Verification error: %s", exc)
        errors.append(f"Verification failed: {exc}")
        return {"verification_result": "UNVERIFIABLE", "processing_errors": errors}
