from __future__ import annotations

from typing import Any

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import RepositoryService


class ValidateNode:
    def __init__(self, repo: RepositoryService) -> None:
        self._repo = repo

    def __call__(self, state: AgentState) -> dict[str, Any]:
        repo_path = state["local_repo_path"]
        attempts = state.get("validation_attempts", 0)
        baseline = state.get("baseline_test_errors", [])

        test_rc, test_output = self._repo.run_go_test(repo_path)
        build_rc, build_output = self._repo.run_go_build(repo_path)

        new_failures = _get_new_failures(test_output, baseline)
        build_failed = build_rc != 0

        if build_failed:
            errors = [_truncate(build_output)]
        elif new_failures:
            errors = [_truncate(test_output)]
        else:
            errors = []

        return {
            "validation_success": not build_failed and not new_failures,
            "validation_errors": errors,
            "validation_attempts": attempts + 1,
        }


def _get_new_failures(output: str, baseline: list[str]) -> list[str]:
    if not baseline:
        return []

    current: set[str] = set()
    for line in output.split("\n"):
        if line.startswith("--- FAIL:"):
            parts = line.split()
            if len(parts) >= 3:
                current.add(parts[2].rstrip("()"))

    baseline_set = set(baseline)
    return list(current - baseline_set)


def _truncate(text: str, max_chars: int = 2000) -> str:
    if len(text) > max_chars:
        return text[:max_chars] + "\n... (truncated)"
    return text
