import subprocess

from agentic_go_contributor.graph.state import AgentState


def validate(state: AgentState) -> dict:
    repo_path = state["local_repo_path"]
    attempts = state.get("validation_attempts", 0)
    baseline = state.get("baseline_test_errors", [])

    test_result = subprocess.run(
        ["go", "test", "./..."],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
    )

    build_result = subprocess.run(
        ["go", "build", "./..."],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
    )

    new_failures = _get_new_failures(test_result.stdout + test_result.stderr, baseline)
    build_failed = build_result.returncode != 0

    if build_failed:
        errors = [_truncate(build_result.stdout + build_result.stderr, 2000)]
    elif new_failures:
        errors = [_truncate(test_result.stdout + test_result.stderr, 2000)]
    else:
        errors = []

    success = not build_failed and not new_failures

    return {
        "validation_success": success,
        "validation_errors": errors,
        "validation_attempts": attempts + 1,
    }


def _get_new_failures(output: str, baseline: list[str]) -> list[str]:
    if not baseline:
        return []

    current = set()
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
