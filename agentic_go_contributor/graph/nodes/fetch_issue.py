from __future__ import annotations

from typing import Any

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import GitHubService


class FetchIssueNode:
    def __init__(self, github: GitHubService) -> None:
        self._github = github

    def __call__(self, state: AgentState) -> dict[str, Any]:
        return {"issue": self._github.fetch_issue(state["repo_url"], state["issue_number"])}
