from backend.models import GhostDeskState


def email_parser_node(state: GhostDeskState) -> dict:
    """Normalize raw email text before processing."""
    email_text = state.get("email_text", "")
    lines = [line.rstrip() for line in email_text.strip().split("\n")]
    normalized = "\n".join(lines)
    return {
        "email_text": normalized,
        "processing_errors": state.get("processing_errors", []),
    }
