from langgraph.graph import StateGraph, END

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.graph.nodes.fetch_issue import fetch_issue
from agentic_go_contributor.graph.nodes.clone_repo import clone_repo
from agentic_go_contributor.graph.nodes.issue_analyzer import analyze_issue
from agentic_go_contributor.graph.nodes.repo_explorer import explore_repo
from agentic_go_contributor.graph.nodes.planner import plan as plan_node
from agentic_go_contributor.graph.nodes.coding_agent import code
from agentic_go_contributor.graph.nodes.validator import validate
from agentic_go_contributor.graph.nodes.human_review import human_review

MAX_ATTEMPTS = 3


def should_retry(state: AgentState) -> str:
    if state.get("validation_attempts", 0) >= MAX_ATTEMPTS:
        return "review"
    if state.get("validation_success", False):
        return "review"
    return "retry"


def human_decision(state: AgentState) -> str:
    if state.get("human_approved", False):
        return "approved"
    if state.get("validation_attempts", 0) >= MAX_ATTEMPTS:
        return "exhausted"
    return "rejected"


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("fetch_issue", fetch_issue)
    workflow.add_node("clone_repo", clone_repo)
    workflow.add_node("analyze_issue", analyze_issue)
    workflow.add_node("explore_repo", explore_repo)
    workflow.add_node("generate_plan", plan_node)
    workflow.add_node("code", code)
    workflow.add_node("validate", validate)
    workflow.add_node("human_review", human_review)

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
            "review": "human_review",
        },
    )

    workflow.add_conditional_edges(
        "human_review",
        human_decision,
        {
            "approved": END,
            "rejected": "code",
            "exhausted": END,
        },
    )

    return workflow.compile()
