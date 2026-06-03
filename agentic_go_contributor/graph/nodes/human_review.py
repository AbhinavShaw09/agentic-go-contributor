import os

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.review.ipc import (
    write_review_request,
    poll_for_decision,
    init_run,
    write_completed,
)


DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")


def human_review(state: AgentState) -> dict:
    success = state.get("validation_success", False)
    attempts = state.get("validation_attempts", 0)

    if not success:
        return {"human_approved": False, "human_feedback": ""}

    if attempts == 0:
        return {"human_approved": True, "human_feedback": ""}

    run_id = state.get("run_id", "")
    repo_url = state.get("repo_url", "")
    issue_number = state.get("issue_number", 0)
    patch = state.get("patch", "")
    plan = state.get("plan", "")
    errors = state.get("validation_errors", [])

    if not run_id:
        print("⚠ No run_id in state — auto-approving")
        return {"human_approved": True, "human_feedback": ""}

    # Ensure run dir exists with status
    init_run(run_id, repo_url, issue_number)

    # Write the review data
    write_review_request(run_id, patch, plan, errors)

    review_url = f"{DASHBOARD_URL}/review/{run_id}"
    print(f"\n  📋 Patch ready for review!")
    print(f"  🔗 Open: {review_url}")
    print(f"  ⏳ Waiting for decision (up to 30 min)...")

    decision = poll_for_decision(run_id)

    if decision is None:
        print("  ⏰ Timed out waiting for review — auto-rejecting")
        return {"human_approved": False, "human_feedback": "Timed out"}

    approved = decision.get("approved", False)
    feedback = decision.get("feedback", "")

    if approved:
        print("  ✅ Patch approved via dashboard")
    else:
        print(f"  ❌ Patch rejected: {feedback[:200] if feedback else 'No feedback'}")

    return {
        "human_approved": approved,
        "human_feedback": feedback,
    }
