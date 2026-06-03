from langgraph.graph import StateGraph, END

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.graph.nodes.fetch_issue import fetch_issue
from agentic_go_contributor.graph.nodes.clone_repo import clone_repo
from agentic_go_contributor.graph.nodes.issue_analyzer import analyze_issue
from agentic_go_contributor.graph.nodes.repo_explorer import explore_repo
from agentic_go_contributor.graph.nodes.planner import plan as plan_node
from agentic_go_contributor.graph.nodes.coding_agent import code
from agentic_go_contributor.graph.nodes.validator import validate

MAX_ATTEMPTS = 3


def should_retry(state: AgentState) -> str:
    if state.get("validation_success", False):
        return "accepted"
    if state.get("validation_attempts", 0) >= MAX_ATTEMPTS:
        return "accepted"
    return "retry"


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("fetch_issue", fetch_issue)
    workflow.add_node("clone_repo", clone_repo)
    workflow.add_node("analyze_issue", analyze_issue)
    workflow.add_node("explore_repo", explore_repo)
    workflow.add_node("generate_plan", plan_node)
    workflow.add_node("code", code)
    workflow.add_node("validate", validate)

    workflow.set_entry_point("fetch_issue")

    workflow.add_edge("fetch_issue", "clone_repo")
    workflow.add_edge("clone_repo", "analyze_issue")
    workflow.add_edge("analyze_issue", "explore_repo")
    workflow.add_edge("explore_repo", "generate_plan")
    workflow.add_edge("generate_plan", "code")
    workflow.add_edge("code", "validate")

    workflow.add_conditional_edges(
        "validate",
        should_retry,
        {
            "retry": "code",
            "accepted": END,
        },
    )

    return workflow.compile()
