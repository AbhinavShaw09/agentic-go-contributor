from __future__ import annotations

import os
from typing import Any

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import ReviewService
from agentic_go_contributor.utils.constants import DASHBOARD_URL_DEFAULT

_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", DASHBOARD_URL_DEFAULT)


class HumanReviewNode:
    def __init__(self, review: ReviewService) -> None:
        self._review = review

    def __call__(self, state: AgentState) -> dict[str, Any]:
        if not state.get("validation_success", False):
            return {"human_approved": False, "human_feedback": ""}
        if state.get("validation_attempts", 0) == 0:
            return {"human_approved": True, "human_feedback": ""}

        run_id = state.get("run_id", "")
        if not run_id:
            print("⚠ No run_id in state — auto-approving")
            return {"human_approved": True, "human_feedback": ""}

        self._review.init_run(run_id, state.get("repo_url", ""), state.get("issue_number", 0))
        self._review.write_review_request(
            run_id,
            state.get("patch", ""),
            state.get("plan", ""),
            state.get("validation_errors", []),
        )

        print(f"\n  📋 Patch ready for review!")
        print(f"  🔗 Open: {_DASHBOARD_URL}/review/{run_id}")
        print(f"  ⏳ Waiting for decision (up to 30 min)...")

        decision = self._review.poll_for_decision(run_id)

        if decision is None:
            print("  ⏰ Timed out waiting for review — auto-rejecting")
            return {"human_approved": False, "human_feedback": "Timed out"}

        approved = decision.get("approved", False)
        feedback = decision.get("feedback", "")

        if approved:
            print("  ✅ Patch approved via dashboard")
        else:
            print(f"  ❌ Patch rejected: {feedback[:200]}")
        return {"human_approved": approved, "human_feedback": feedback}
