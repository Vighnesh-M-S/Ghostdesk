import io
import json
import logging
import os
from backend.models import GhostDeskState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM = """You are a document analysis expert for customer support.

Extract key information from the document content provided.

Respond with ONLY a valid JSON object:
{
    "document_type": "invoice|receipt|screenshot|contract|other",
    "summary": "Brief 1-2 sentence summary",
    "key_entities": {
        "amounts": ["monetary amounts found"],
        "dates": ["dates found"],
        "ids": ["booking IDs, order IDs, reference numbers"],
        "parties": ["company or merchant names"]
    },
    "evidence": ["specific facts that could verify customer claims"],
    "important_values": {
        "total_amount": "main amount if present, else null",
        "date": "main date if present, else null",
        "reference": "main reference ID if present, else null"
    }
}"""


def _extract_pdf_text(content: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            parts = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(parts).strip()
    except Exception as e1:
        logger.warning("pdfplumber failed (%s), trying pymupdf", e1)
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in doc).strip()
    except Exception as e2:
        logger.error("PDF extraction failed: %s", e2)
        return ""


def _extract_image_text(content: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
        image = Image.open(io.BytesIO(content))
        return pytesseract.image_to_string(image).strip()
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def _parse_json(content: str) -> dict:
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def attachment_analysis_node(state: GhostDeskState) -> dict:
    """Extract text from attachments and generate structured summaries."""
    attachments = state.get("attachments", [])
    errors = list(state.get("processing_errors", []))

    if not attachments:
        return {"attachment_summary": "No attachments provided.", "processing_errors": errors}

    try:
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.1,
        )

        enriched_attachments = []
        all_analyses = []

        for att in attachments:
            filename = att.get("filename", "unknown")
            file_type = att.get("type", "").lower()
            content: bytes = att.get("content", b"")

            if not content:
                enriched_attachments.append({**att, "analysis": {}, "content": content})
                continue

            # Extract text
            if file_type in ("pdf", "application/pdf"):
                text = _extract_pdf_text(content)
            elif file_type in ("png", "jpg", "jpeg", "image/png", "image/jpeg"):
                text = _extract_image_text(content)
            else:
                text = _extract_pdf_text(content) or _extract_image_text(content)

            if not text:
                enriched_attachments.append({**att, "analysis": {"summary": "Could not extract text."}, "content": content})
                continue

            truncated = text[:3000] + ("...[truncated]" if len(text) > 3000 else "")
            response = llm.invoke([
                SystemMessage(content=_ANALYSIS_SYSTEM),
                HumanMessage(content=f"Document: {filename}\n\nContent:\n{truncated}"),
            ])
            analysis = _parse_json(response.content)
            analysis["filename"] = filename
            all_analyses.append(analysis)
            enriched_attachments.append({**att, "analysis": analysis, "content": content})

        # Human-readable combined summary
        if all_analyses:
            summary_prompt = "Summarize the key findings from these document analyses in 2–3 sentences for a support agent."
            sr = llm.invoke([
                SystemMessage(content=summary_prompt),
                HumanMessage(content=json.dumps(all_analyses, indent=2)),
            ])
            human_summary = sr.content.strip()
        else:
            human_summary = f"{len(attachments)} file(s) provided but no text could be extracted."

        return {
            "attachment_summary": human_summary,
            "attachments": enriched_attachments,
            "processing_errors": errors,
        }

    except Exception as exc:
        logger.error("Attachment analysis error: %s", exc)
        errors.append(f"Attachment analysis failed: {exc}")
        return {
            "attachment_summary": f"{len(attachments)} file(s) provided. Analysis failed.",
            "processing_errors": errors,
        }
