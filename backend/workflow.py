from langgraph.graph import StateGraph, START, END
from backend.models import GhostDeskState
from backend.agents.email_parser import email_parser_node
from backend.agents.pii_redaction import pii_redaction_node
from backend.agents.intent_classification import intent_classification_node
from backend.agents.attachment_analysis import attachment_analysis_node
from backend.agents.verification import verification_node
from backend.agents.risk_detection import risk_detection_node
from backend.agents.resolution import resolution_node
from backend.agents.human_approval import human_approval_node


def build_workflow():
    graph = StateGraph(GhostDeskState)

    graph.add_node("email_parser", email_parser_node)
    graph.add_node("pii_redaction", pii_redaction_node)
    graph.add_node("intent_classification", intent_classification_node)
    graph.add_node("attachment_analysis", attachment_analysis_node)
    graph.add_node("verification", verification_node)
    graph.add_node("risk_detection", risk_detection_node)
    graph.add_node("resolution", resolution_node)
    graph.add_node("human_approval", human_approval_node)

    graph.add_edge(START, "email_parser")
    graph.add_edge("email_parser", "pii_redaction")
    graph.add_edge("pii_redaction", "intent_classification")
    graph.add_edge("intent_classification", "attachment_analysis")
    graph.add_edge("attachment_analysis", "verification")
    graph.add_edge("verification", "risk_detection")
    graph.add_edge("risk_detection", "resolution")
    graph.add_edge("resolution", "human_approval")
    graph.add_edge("human_approval", END)

    return graph.compile()


workflow = build_workflow()
