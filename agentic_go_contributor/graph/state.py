from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    run_id: str
    repo_url: str
    issue_number: int
    local_repo_path: str
    issue: dict[str, Any]
    issue_type: str
    issue_summary: str
    issue_constraints: list[str]
    relevant_files: list[str]
    relevant_tests: list[str]
    repository_context: dict[str, str]
    plan: str
    patch: str
    baseline_test_errors: list[str]
    validation_attempts: int
    validation_success: bool
    validation_errors: list[str]
    human_approved: bool
    human_feedback: str
