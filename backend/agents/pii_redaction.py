import re
import logging
from backend.models import GhostDeskState

logger = logging.getLogger(__name__)

_REPLACEMENTS = {
    "PERSON": "[NAME]",
    "PHONE_NUMBER": "[PHONE_NUMBER]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "CREDIT_CARD": "[CREDIT_CARD]",
    "LOCATION": "[ADDRESS]",
    "US_BANK_NUMBER": "[ACCOUNT_NUMBER]",
    "US_SSN": "[SSN]",
    "IBAN_CODE": "[ACCOUNT_NUMBER]",
    "IN_PAN": "[PAN]",
    "IN_AADHAAR": "[AADHAAR]",
    "DEFAULT": "[REDACTED]",
}


def _regex_redact(text: str) -> str:
    """Regex-based fallback PII redaction."""
    # Email addresses
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text)
    # Indian mobile numbers
    text = re.sub(r"\b(?:\+91[-.\s]?)?[6-9]\d{9}\b", "[PHONE_NUMBER]", text)
    # Generic 10-11 digit numbers
    text = re.sub(r"\b\d{10,11}\b", "[PHONE_NUMBER]", text)
    # International phone numbers
    text = re.sub(r"\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE_NUMBER]", text)
    # Credit / debit card numbers (4×4 digit groups)
    text = re.sub(r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[CREDIT_CARD]", text)
    # Indian PAN
    text = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "[PAN]", text)
    # Aadhaar (12 digits, optionally spaced as 4-4-4)
    text = re.sub(r"\b\d{4}\s\d{4}\s\d{4}\b", "[AADHAAR]", text)
    # Street addresses (simplified)
    text = re.sub(
        r"\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Boulevard|Blvd)\b",
        "[ADDRESS]",
        text,
        flags=re.IGNORECASE,
    )
    return text


def pii_redaction_node(state: GhostDeskState) -> dict:
    """Detect and redact PII from email text using Presidio with regex fallback."""
    email_text = state.get("email_text", "")
    errors = list(state.get("processing_errors", []))

    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig

        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()

        entities = [
            "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD",
            "LOCATION", "US_BANK_NUMBER", "US_SSN", "IBAN_CODE",
        ]
        results = analyzer.analyze(text=email_text, entities=entities, language="en")

        operators = {
            entity: OperatorConfig("replace", {"new_value": _REPLACEMENTS.get(entity, "[REDACTED]")})
            for entity in entities
        }
        operators["DEFAULT"] = OperatorConfig("replace", {"new_value": "[REDACTED]"})

        anonymized = anonymizer.anonymize(text=email_text, analyzer_results=results, operators=operators)
        redacted_text = anonymized.text

    except ImportError:
        logger.warning("Presidio unavailable — using regex redaction")
        redacted_text = _regex_redact(email_text)
    except Exception as exc:
        logger.error("PII redaction error: %s", exc)
        errors.append(f"PII redaction partial: {exc}")
        redacted_text = _regex_redact(email_text)

    return {"redacted_email": redacted_text, "processing_errors": errors}
