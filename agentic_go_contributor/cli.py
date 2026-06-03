import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv

from agentic_go_contributor.graph.graph import build_graph
from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.review.ipc import init_run, write_completed

load_dotenv(dotenv_path=Path(__file__).parent.parent / "etc" / ".env")

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")
RESULTS_DIR = Path(__file__).parent.parent / "results"


@click.command()
@click.option("--repo", required=True, help="Repository URL or owner/name (e.g. spf13/cobra)")
@click.option("--issue", required=True, type=int, help="Issue number (e.g. 1234)")
@click.option("--run-id", default="", help="Unique run ID (auto-generated if empty)")
def main(repo: str, issue: int, run_id: str) -> None:
    if "OPENROUTER_API_KEY" not in os.environ:
        click.echo("Error: OPENROUTER_API_KEY environment variable is required", err=True)
        sys.exit(1)

    if not run_id:
        run_id = str(uuid.uuid4())[:8]

    initial_state: AgentState = {
        "run_id": run_id,
        "repo_url": repo,
        "issue_number": issue,
        "local_repo_path": "",
        "issue": {},
        "issue_type": "",
        "issue_summary": "",
        "issue_constraints": [],
        "relevant_files": [],
        "relevant_tests": [],
        "repository_context": {},
        "plan": "",
        "patch": "",
        "baseline_test_errors": [],
        "validation_attempts": 0,
        "validation_success": False,
        "validation_errors": [],
        "human_approved": False,
        "human_feedback": "",
    }

    click.echo(f"🚀 Resolving issue #{issue} in {repo}...")
    click.echo(f"   Run ID: {run_id}")
    click.echo(f"   Dashboard: {DASHBOARD_URL}/review/{run_id}\n")

    # Init the IPC run directory
    init_run(run_id, repo, issue)

    try:
        graph = build_graph()
        final_state = graph.invoke(initial_state)
    except Exception as e:
        click.echo(f"Error during execution: {e}", err=True)
        sys.exit(1)

    _print_output(final_state)
    _save_results(final_state)
    write_completed(run_id, final_state)
    dashboard_url = f"{DASHBOARD_URL}/review/{run_id}"
    click.echo(f"\n🔗 Dashboard: {dashboard_url}")


def _print_output(state: AgentState) -> None:
    click.echo("")

    if state.get("issue_type"):
        click.echo(f"✓ Issue analyzed ({state['issue_type']}: {state.get('issue_summary', '')})")
    if state.get("relevant_files"):
        click.echo(f"✓ Repository explored ({len(state['relevant_files'])} files, {len(state.get('relevant_tests', []))} tests)")
    if state.get("plan"):
        click.echo("✓ Plan generated")
    if state.get("patch"):
        click.echo("✓ Code modified")
    if state.get("validation_success"):
        click.echo("✓ Tests passed")
    elif state.get("validation_errors"):
        click.echo("✗ Tests failed (check output below)")
    if state.get("human_approved"):
        click.echo("✓ Human approved")
    elif state.get("human_feedback"):
        click.echo(f"✗ Human rejected: {state['human_feedback'][:100]}")

    click.echo("")
    click.echo("--- Patch ---")
    click.echo(state.get("patch", "(no patch generated)"))

    click.echo("")
    click.echo("--- Summary ---")
    click.echo(f"Issue: #{state.get('issue_number', '?')}")
    click.echo(f"Type: {state.get('issue_type', '?')}")
    click.echo(f"Human approved: {state.get('human_approved', False)}")
    click.echo(f"Attempts: {state.get('validation_attempts', 0)}")

    if state.get("validation_success"):
        click.echo("Tests: passed")
    elif state.get("validation_errors"):
        click.echo("Errors:")
        for err in state["validation_errors"]:
            for line in err.split("\n")[:10]:
                click.echo(f"  {line}")


def _save_results(state: AgentState) -> None:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    repo = state.get("repo_url", "unknown").replace("/", "_").replace("https://github.com/", "")
    issue = state.get("issue_number", "?")
    run_dir = RESULTS_DIR / f"{repo}_issue-{issue}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

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
        "timestamp": ts,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    if state.get("plan"):
        (run_dir / "plan.md").write_text(state["plan"] + "\n")
    patch = state.get("patch", "")
    (run_dir / "patch.diff").write_text(patch if patch else "(no patch generated)\n")
    if state.get("validation_errors"):
        (run_dir / "test_results.txt").write_text(
            "\n\n".join(state["validation_errors"]) + "\n"
        )
    click.echo(f"\n📁 Results saved to: {run_dir}")


if __name__ == "__main__":
    main()
