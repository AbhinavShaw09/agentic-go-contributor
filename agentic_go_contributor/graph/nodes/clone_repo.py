import subprocess

from agentic_go_contributor.repository.clone import clone_repo as _clone_repo
from agentic_go_contributor.graph.state import AgentState


def clone_repo(state: AgentState) -> dict:
    local_path = _clone_repo(state["repo_url"])

    errors = _run_baseline_tests(local_path)

    return {
        "local_repo_path": local_path,
        "baseline_test_errors": errors,
    }


def _run_baseline_tests(repo_path: str) -> list[str]:
    result = subprocess.run(
        ["go", "test", "./...", "2>&1"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        return []

    errors = []
    output = result.stdout + result.stderr
    for line in output.split("\n"):
        if line.startswith("--- FAIL:"):
            parts = line.split()
            if len(parts) >= 3:
                errors.append(parts[2].rstrip("()"))
    return errors
