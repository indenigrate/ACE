import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import AgentState
from src.nodes import (
    fetch_lead_node,
    validate_emails_node,
    research_node,
    generate_draft_node,
    refine_draft_node,
    send_email_node,
    update_sheet_node,
    human_review_node
)
from config.settings import MAX_REFINEMENT_ITERATIONS

logger = logging.getLogger(__name__)


def check_email_count(state: AgentState):
    """Conditional edge to skip if no email found."""
    if state.get("status") == "end":
        return "end"
    if not state.get("candidate_emails") or len(state["candidate_emails"]) == 0:
        return "skip"
    return "continue"


def human_review_router(state: AgentState):
    """Router for human feedback with iteration guardrail."""
    if state.get("mode") == "auto_draft":
        return "send"

    status = state.get("status")
    iteration_count = state.get("iteration_count", 0)

    # Guardrail: prevent infinite refinement loops
    if status == "refining" and iteration_count >= MAX_REFINEMENT_ITERATIONS:
        logger.warning(
            f"Max refinement iterations ({MAX_REFINEMENT_ITERATIONS}) reached. "
            "Forcing send."
        )
        return "send"

    if status == "approved":
        return "send"
    if status == "skipped":
        return "update"
    if status == "refining":
        return "refine"
    return "review"


def create_graph(autonomous: bool = False):
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("fetch", fetch_lead_node)
    workflow.add_node("validate", validate_emails_node)
    workflow.add_node("research", research_node)
    workflow.add_node("generate", generate_draft_node)
    workflow.add_node("review", human_review_node)
    workflow.add_node("refine", refine_draft_node)
    workflow.add_node("send", send_email_node)
    workflow.add_node("update", update_sheet_node)

    # Add Edges
    workflow.set_entry_point("fetch")

    # fetch → validate (always)
    workflow.add_edge("fetch", "validate")

    # validate → check if emails survived validation
    workflow.add_conditional_edges(
        "validate",
        check_email_count,
        {
            "continue": "research",
            "skip": "update",
            "end": END
        }
    )

    workflow.add_edge("research", "generate")
    workflow.add_edge("generate", "review")
    workflow.add_edge("refine", "review")

    workflow.add_conditional_edges(
        "review",
        human_review_router,
        {
            "send": "send",
            "refine": "refine",
            "update": "update",
            "review": "review"
        }
    )

    workflow.add_edge("send", "update")
    workflow.add_edge("update", "fetch")

    # Checkpointer for persistence
    memory = MemorySaver()

    interrupts = [] if autonomous else ["review"]

    return workflow.compile(
        checkpointer=memory,
        interrupt_before=interrupts
    )