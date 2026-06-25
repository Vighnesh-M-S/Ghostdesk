from backend.models import GhostDeskState

CONFIDENCE_THRESHOLD = 0.80
RISK_THRESHOLD = 0.70


def human_approval_node(state: GhostDeskState) -> dict:
    """Decide whether human review is required and assemble the final output."""
    confidence = state.get("intent_confidence", 0.5)
    risk_score = state.get("risk_score", 0.5)
    verification_result = state.get("verification_result", "")
    errors = list(state.get("processing_errors", []))

    requires_human = False
    reasons: list[str] = []

    if confidence < CONFIDENCE_THRESHOLD:
        requires_human = True
        reasons.append(f"Low confidence ({confidence:.0%} < {CONFIDENCE_THRESHOLD:.0%} threshold)")

    if risk_score > RISK_THRESHOLD:
        requires_human = True
        reasons.append(f"High risk score ({risk_score:.2f} > {RISK_THRESHOLD:.2f} threshold)")

    if verification_result == "MISMATCH":
        requires_human = True
        reasons.append("Claim verification failed — document evidence contradicts email claims")

    final_output = {
        "redacted_email": state.get("redacted_email", ""),
        "intent": state.get("intent", ""),
        "intent_confidence": confidence,
        "attachment_summary": state.get("attachment_summary", ""),
        "verification_result": verification_result,
        "risk_score": risk_score,
        "risk_flags": state.get("risk_flags", []),
        "recommended_action": state.get("recommended_action", ""),
        "resolution_summary": state.get("resolution_summary", ""),
        "requires_human_review": requires_human,
        "human_review_reasons": reasons,
        "processing_errors": errors,
    }

    return {
        "requires_human_review": requires_human,
        "final_output": final_output,
        "processing_errors": errors,
    }
