import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "runs"


def _run_dir(run_id: str) -> Path:
    return DATA_DIR / run_id


def init_run(run_id: str, repo_url: str, issue_number: int) -> Path:
    d = _run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    _write_status(d, "running", repo_url, issue_number)
    return d


def _write_status(
    path: Path,
    status: str,
    repo_url: str = "",
    issue_number: int = 0,
):
    status_path = path / "status.json"
    current = {}
    if status_path.exists():
        current = json.loads(status_path.read_text())
    current.update(
        {
            "status": status,
            "repo_url": repo_url or current.get("repo_url", ""),
            "issue_number": issue_number or current.get("issue_number", 0),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    status_path.write_text(json.dumps(current, indent=2) + "\n")


def write_review_request(run_id: str, patch: str, plan: str, errors: list[str]):
    d = _run_dir(run_id)
    review = {
        "patch": patch,
        "plan": plan,
        "errors": errors,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (d / "review.json").write_text(json.dumps(review, indent=2) + "\n")
    status_path = d / "status.json"
    current = json.loads(status_path.read_text()) if status_path.exists() else {}
    current["status"] = "pending_review"
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    status_path.write_text(json.dumps(current, indent=2) + "\n")


def poll_for_decision(
    run_id: str,
    timeout_minutes: int = 30,
    interval_seconds: int = 5,
) -> Optional[dict]:
    decision_path = _run_dir(run_id) / "decision.json"
    start = time.time()
    timeout = timeout_minutes * 60

    while time.time() - start < timeout:
        if decision_path.exists():
            decision = json.loads(decision_path.read_text())
            return decision
        remaining = int(timeout - (time.time() - start))
        mins, secs = divmod(remaining, 60)
        print(f"  ⏳ Waiting for review... ({mins:02d}:{secs:02d} remaining)", end="\r")
        time.sleep(interval_seconds)

    print()
    return None


def write_decision(run_id: str, approved: bool, feedback: str = ""):
    d = _run_dir(run_id)
    decision = {
        "approved": approved,
        "feedback": feedback,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    (d / "decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    status = "approved" if approved else "rejected"
    status_path = d / "status.json"
    current = json.loads(status_path.read_text()) if status_path.exists() else {}
    current["status"] = status
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    status_path.write_text(json.dumps(current, indent=2) + "\n")


def write_completed(run_id: str, state: dict):
    d = _run_dir(run_id)
    summary = {
        "repo": state.get("repo_url", ""),
        "issue": state.get("issue_number", 0),
        "issue_title": state.get("issue", {}).get("title", ""),
        "issue_type": state.get("issue_type", ""),
        "issue_summary": state.get("issue_summary", ""),
        "relevant_files_count": len(state.get("relevant_files", [])),
        "relevant_tests_count": len(state.get("relevant_tests", [])),
        "validation_success": state.get("validation_success", False),
        "validation_attempts": state.get("validation_attempts", 0),
        "validation_errors": state.get("validation_errors", []),
        "human_approved": state.get("human_approved", False),
        "human_feedback": state.get("human_feedback", ""),
        "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
    }
    (d / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if state.get("plan"):
        (d / "plan.md").write_text(state["plan"] + "\n")
    patch = state.get("patch", "")
    (d / "patch.diff").write_text(patch if patch else "(no patch generated)\n")
    if state.get("validation_errors"):
        (d / "test_results.txt").write_text(
            "\n\n".join(state["validation_errors"]) + "\n"
        )
    _write_status(d, "completed")


def get_run_status(run_id: str) -> Optional[dict]:
    status_path = _run_dir(run_id) / "status.json"
    if not status_path.exists():
        return None
    return json.loads(status_path.read_text())


def list_runs(limit: int = 20) -> list[dict]:
    if not DATA_DIR.exists():
        return []
    runs = []
    for d in sorted(DATA_DIR.iterdir(), reverse=True):
        status_path = d / "status.json"
        if status_path.exists():
            info = json.loads(status_path.read_text())
            info["run_id"] = d.name
            runs.append(info)
    return runs[:limit]


def get_review(run_id: str) -> Optional[dict]:
    review_path = _run_dir(run_id) / "review.json"
    if not review_path.exists():
        return None
    return json.loads(review_path.read_text())
