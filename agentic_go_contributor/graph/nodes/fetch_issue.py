from agentic_go_contributor.github.issue_service import fetch_issue as _fetch_issue
from agentic_go_contributor.graph.state import AgentState


def fetch_issue(state: AgentState) -> dict:
    issue = _fetch_issue(state["repo_url"], state["issue_number"])
    return {"issue": issue}
