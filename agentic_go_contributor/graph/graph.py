from langgraph.graph import END, StateGraph

from agentic_go_contributor.graph.nodes.clone_repo import CloneRepoNode
from agentic_go_contributor.graph.nodes.coding_agent import CodingAgentNode
from agentic_go_contributor.graph.nodes.fetch_issue import FetchIssueNode
from agentic_go_contributor.graph.nodes.human_review import HumanReviewNode
from agentic_go_contributor.graph.nodes.issue_analyzer import AnalyzeIssueNode
from agentic_go_contributor.graph.nodes.planner import PlanNode
from agentic_go_contributor.graph.nodes.repo_explorer import ExploreRepoNode
from agentic_go_contributor.graph.nodes.validator import ValidateNode
from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import Services
from agentic_go_contributor.utils.constants import REPAIR_MAX_ATTEMPTS


def _should_retry(state: AgentState) -> str:
    if state.get("validation_attempts", 0) >= REPAIR_MAX_ATTEMPTS:
        return "review"
    if state.get("validation_success", False):
        return "review"
    return "retry"


def _human_decision(state: AgentState) -> str:
    if state.get("human_approved", False):
        return "approved"
    if state.get("validation_attempts", 0) >= REPAIR_MAX_ATTEMPTS:
        return "exhausted"
    return "rejected"


def build_graph(services: Services) -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("fetch_issue", FetchIssueNode(services.github))
    workflow.add_node("clone_repo", CloneRepoNode(services.repo))
    workflow.add_node("analyze_issue", AnalyzeIssueNode(services.llm))
    workflow.add_node("explore_repo", ExploreRepoNode(services.repo))
    workflow.add_node("generate_plan", PlanNode(services.llm))
    workflow.add_node("code", CodingAgentNode(services.llm, services.repo))
    workflow.add_node("validate", ValidateNode(services.repo))
    workflow.add_node("human_review", HumanReviewNode(services.review))

    workflow.set_entry_point("fetch_issue")

    workflow.add_edge("fetch_issue", "clone_repo")
    workflow.add_edge("clone_repo", "analyze_issue")
    workflow.add_edge("analyze_issue", "explore_repo")
    workflow.add_edge("explore_repo", "generate_plan")
    workflow.add_edge("generate_plan", "code")
    workflow.add_edge("code", "validate")

    workflow.add_conditional_edges(
        "validate",
        _should_retry,
        {"retry": "code", "review": "human_review"},
    )

    workflow.add_conditional_edges(
        "human_review",
        _human_decision,
        {"approved": END, "rejected": "code", "exhausted": END},
    )

    return workflow.compile()
