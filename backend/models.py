from typing import TypedDict, List, Any, Optional
from pydantic import BaseModel


class GhostDeskState(TypedDict):
    email_text: str
    redacted_email: str
    intent: str
    intent_confidence: float
    attachments: List[Any]
    attachment_summary: str
    verification_result: str
    risk_flags: List[str]
    risk_score: float
    recommended_action: str
    resolution_summary: str
    requires_human_review: bool
    final_output: Any
    processing_errors: List[str]


class ProcessResponse(BaseModel):
    success: bool
    data: dict
    error: Optional[str] = None
