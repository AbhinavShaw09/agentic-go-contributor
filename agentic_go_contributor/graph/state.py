from typing import TypedDict


class AgentState(TypedDict):
    run_id: str
    repo_url: str
    issue_number: int
    local_repo_path: str

    issue: dict

    issue_type: str
    issue_summary: str
    issue_constraints: list[str]

    relevant_files: list[str]
    relevant_tests: list[str]
    repository_context: dict

    plan: str

    patch: str

    baseline_test_errors: list[str]

    validation_attempts: int
    validation_success: bool
    validation_errors: list[str]

    human_approved: bool
    human_feedback: str
