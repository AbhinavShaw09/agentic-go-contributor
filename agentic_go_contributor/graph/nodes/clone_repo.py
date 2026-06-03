from __future__ import annotations

from typing import Any

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import RepositoryService


class CloneRepoNode:
    def __init__(self, repo: RepositoryService) -> None:
        self._repo = repo

    def __call__(self, state: AgentState) -> dict[str, Any]:
        local_path = self._repo.clone(state["repo_url"])
        errors = self._repo.run_baseline_tests(local_path)
        return {"local_repo_path": local_path, "baseline_test_errors": errors}
