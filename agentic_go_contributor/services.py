from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agentic_go_contributor.repository.clone import (
    clone_repo as _clone_repo,
    get_diff as _get_diff,
    reset_hard as _reset_hard,
)
from agentic_go_contributor.repository.code_search import (
    find_files_by_keywords as _find_files_by_keywords,
    find_related_tests as _find_related_tests,
    list_go_files as _list_go_files,
    read_file_contents as _read_file_contents,
)
from agentic_go_contributor.utils.constants import (
    GO_BUILD_TIMEOUT,
    GO_TEST_TIMEOUT,
    LLM_MAX_RETRIES,
    LLM_RETRY_BASE_DELAY,
    REVIEW_POLL_INTERVAL,
    REVIEW_TIMEOUT_MINUTES,
)
from agentic_go_contributor.utils.repo_url import parse_repo_url

# ── LLM ───────────────────────────────────────────────────────────────


class LLMService:
    def __init__(
        self,
        model: str = "",
        max_tokens: int = 0,
    ) -> None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            print("Error: OPENROUTER_API_KEY is not set", file=sys.stderr)
            sys.exit(1)
        self._api_key = api_key
        self._default_model = model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self._max_tokens = max_tokens or int(os.environ.get("OPENROUTER_MAX_TOKENS", "1024"))

    def get_chat(self, model: str = "") -> ChatOpenAI:
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self._api_key,
            model=model or self._default_model,
            temperature=0.1,
            max_tokens=self._max_tokens,
        )

    def invoke(self, system: str, user: str, model: str = "") -> str:
        llm = self.get_chat(model)

        def _call() -> Any:
            return llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])

        result = _llm_call_with_retry(_call)
        if hasattr(result, "content"):
            return result.content
        return str(result)


def _llm_call_with_retry(fn: Callable[[], Any]) -> Any:
    for retry in range(LLM_MAX_RETRIES):
        try:
            return fn()
        except Exception as e:
            if retry == LLM_MAX_RETRIES - 1:
                raise
            if "429" in str(e) or "503" in str(e):
                time.sleep(LLM_RETRY_BASE_DELAY * (2 ** retry))
            else:
                time.sleep(2)
    return ""


# ── GitHub ───────────────────────────────────────────────────────────


class GitHubService:
    GITHUB_API_BASE = "https://api.github.com"

    def __init__(self, token: str = "") -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN", "")

    def fetch_issue(self, repo_url: str, issue_number: int) -> dict[str, Any]:
        owner, repo = parse_repo_url(repo_url)
        headers = self._headers()
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"

        with httpx.Client() as client:
            resp = client.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            issue: dict[str, Any] = resp.json()

            comments_resp = client.get(
                f"{issue['url']}/comments",
                headers=headers,
                timeout=30,
            )
            if comments_resp.status_code == 200:
                issue["comments_data"] = [
                    {"body": c["body"], "author": c["user"]["login"]}
                    for c in comments_resp.json()
                ]

        return {
            "title": issue.get("title", ""),
            "body": issue.get("body", ""),
            "labels": [l["name"] for l in issue.get("labels", [])],
            "state": issue.get("state", ""),
            "comments": issue.get("comments_data", []),
            "url": issue.get("html_url", ""),
        }

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "agentic-go-contributor",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers


# ── Repository ───────────────────────────────────────────────────────


class RepositoryService:
    @staticmethod
    def clone(repo_url: str) -> str:
        return _clone_repo(repo_url)

    @staticmethod
    def get_diff(repo_path: str) -> str:
        return _get_diff(repo_path)

    @staticmethod
    def reset_hard(repo_path: str) -> None:
        _reset_hard(repo_path)

    @staticmethod
    def search_files(repo_path: str, keywords: list[str]) -> list[str]:
        return _find_files_by_keywords(repo_path, keywords)

    @staticmethod
    def find_tests(repo_path: str, source_files: list[str]) -> list[str]:
        return _find_related_tests(repo_path, source_files)

    @staticmethod
    def read_files(repo_path: str, files: list[str]) -> dict[str, str]:
        return _read_file_contents(repo_path, files)

    @staticmethod
    def list_go_files(repo_path: str) -> list[str]:
        return _list_go_files(repo_path)

    @staticmethod
    def run_go_test(repo_path: str) -> tuple[int, str]:
        result = subprocess.run(
            ["go", "test", "./..."],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=GO_TEST_TIMEOUT,
        )
        return result.returncode, result.stdout + result.stderr

    @staticmethod
    def run_go_build(repo_path: str) -> tuple[int, str]:
        result = subprocess.run(
            ["go", "build", "./..."],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=GO_BUILD_TIMEOUT,
        )
        return result.returncode, result.stdout + result.stderr

    @staticmethod
    def run_baseline_tests(repo_path: str) -> list[str]:
        returncode, output = RepositoryService.run_go_test(repo_path)
        if returncode == 0:
            return []
        errors = []
        for line in output.split("\n"):
            if line.startswith("--- FAIL:"):
                parts = line.split()
                if len(parts) >= 3:
                    errors.append(parts[2].rstrip("()"))
        return errors


# ── Review (file-based IPC) ──────────────────────────────────────────


class ReviewService:
    def __init__(self, data_dir: str = "") -> None:
        if data_dir:
            self._base = Path(data_dir)
        else:
            self._base = Path(__file__).parent.parent / "data" / "runs"

    def init_run(self, run_id: str, repo_url: str, issue_number: int) -> None:
        d = self._run_dir(run_id)
        d.mkdir(parents=True, exist_ok=True)
        self._set_status(run_id, "running", repo_url=repo_url, issue_number=issue_number)

    def write_review_request(self, run_id: str, patch: str, plan: str, errors: list[str]) -> None:
        d = self._run_dir(run_id)
        self._write_json(d / "review.json", {
            "patch": patch,
            "plan": plan,
            "errors": errors,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self._set_status(run_id, "pending_review")

    def poll_for_decision(self, run_id: str) -> Optional[dict[str, Any]]:
        decision_path = self._run_dir(run_id) / "decision.json"
        start = time.time()
        timeout = REVIEW_TIMEOUT_MINUTES * 60

        while time.time() - start < timeout:
            if decision_path.exists():
                return self._read_json(decision_path)
            remaining = int(timeout - (time.time() - start))
            mins, secs = divmod(remaining, 60)
            print(f"  ⏳ Waiting for review... ({mins:02d}:{secs:02d})", end="\r")
            time.sleep(REVIEW_POLL_INTERVAL)

        print()
        return None

    def write_completed(self, run_id: str, state: dict[str, Any]) -> None:
        d = self._run_dir(run_id)
        self._write_json(d / "summary.json", {
            "repo": state.get("repo_url", ""),
            "issue": state.get("issue_number", 0),
            "issue_title": state.get("issue", {}).get("title", ""),
            "issue_type": state.get("issue_type", ""),
            "issue_summary": state.get("issue_summary", ""),
            "validation_success": state.get("validation_success", False),
            "validation_attempts": state.get("validation_attempts", 0),
            "human_approved": state.get("human_approved", False),
            "human_feedback": state.get("human_feedback", ""),
            "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        })
        if state.get("plan"):
            (d / "plan.md").write_text(state["plan"] + "\n")
        patch = state.get("patch", "")
        (d / "patch.diff").write_text(patch if patch else "(no patch generated)\n")
        if state.get("validation_errors"):
            (d / "test_results.txt").write_text(
                "\n\n".join(state["validation_errors"]) + "\n"
            )
        self._set_status(run_id, "completed")

    def _run_dir(self, run_id: str) -> Path:
        return self._base / run_id

    @staticmethod
    def _read_json(path: Path) -> dict:
        if path.exists():
            return json.loads(path.read_text())
        return {}

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2) + "\n")

    def _set_status(self, run_id: str, status: str, **extra: Any) -> None:
        status_path = self._run_dir(run_id) / "status.json"
        current = self._read_json(status_path)
        current.update(
            status=status,
            updated_at=datetime.now(timezone.utc).isoformat(),
            **extra,
        )
        self._write_json(status_path, current)


# ── Service container ────────────────────────────────────────────────


@dataclass
class Services:
    llm: LLMService = field(default_factory=LLMService)
    github: GitHubService = field(default_factory=GitHubService)
    repo: RepositoryService = field(default_factory=RepositoryService)
    review: ReviewService = field(default_factory=ReviewService)
