from __future__ import annotations

import os
import re
from typing import Any

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import LLMService, RepositoryService
from agentic_go_contributor.utils.constants import DASHBOARD_URL_DEFAULT

_CODE_MODEL = "openai/gpt-4o-mini"
_MAX_CONTEXT = 15000
_MAX_ERROR = 500

_SYSTEM = (
    "You are a Go engineer. Given a plan and source files, you must output SEARCH/REPLACE blocks "
    "to modify the code. Each block specifies exact text to find and the text to replace it with.\n\n"
    "Format for each block:\n"
    "FILE: path/to/file.go\n"
    "SEARCH\n"
    "<exact lines to find>\n"
    "REPLACE\n"
    "<new lines to replace with>\n\n"
    "Rules:\n"
    "- The SEARCH text must MATCH EXACTLY the current file content, including whitespace\n"
    "- Only include enough context in SEARCH to make the match unique\n"
    "- Make minimal changes (don't reformat entire files)\n"
    "- Multiple SEARCH/REPLACE blocks can be in one file for different locations\n"
    "- If no changes are needed to a file, omit it entirely"
)


class CodingAgentNode:
    def __init__(self, llm: LLMService, repo: RepositoryService) -> None:
        self._llm = llm
        self._repo = repo

    def __call__(self, state: AgentState) -> dict[str, Any]:
        repo_path = state["local_repo_path"]
        files = state.get("relevant_files", [])
        context = state.get("repository_context", {})
        errors = state.get("validation_errors", [])
        attempt = state.get("validation_attempts", 0)

        self._repo.reset_hard(repo_path)

        targets = [f for f in files if not f.startswith("go.")][:2]
        context_text = _build_context(targets, context)
        errors_text = _build_errors(errors, attempt)

        user = (
            f"Issue: {state.get('issue_type', '')} - {state.get('issue_summary', '')}\n\n"
            f"Plan:\n{state.get('plan', '')}\n\n"
            f"Files to modify and their current contents:\n{context_text}\n\n"
            f"Previous errors to fix:\n{errors_text}\n\n"
            "Output SEARCH/REPLACE blocks for each change needed. "
            "Make sure SEARCH text matches the current file content exactly."
        )

        output = self._llm.invoke(_SYSTEM, user, _CODE_MODEL)
        _apply_blocks(repo_path, output, targets, context)

        return {"patch": self._repo.get_diff(repo_path)}


def _build_context(files: list[str], context: dict[str, str]) -> str:
    remaining = _MAX_CONTEXT
    lines: list[str] = []
    for f in files:
        content = context.get(f, "")
        if not content:
            continue
        chunk = content[:remaining]
        lines.append(f"--- {f}\n{chunk}")
        if len(content) > remaining:
            lines.append("... (truncated)")
        lines.append("")
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return "\n".join(lines)


def _build_errors(errors: list[str], attempt: int) -> str:
    if not errors or attempt == 0:
        return "None"
    truncated = [e[:_MAX_ERROR] for e in errors]
    return "\n".join(f"- {e}" for e in truncated)


def _apply_blocks(
    repo_path: str,
    output: str,
    expected_files: list[str],
    originals: dict[str, str],
) -> None:
    blocks = re.split(r'^FILE:\s*(\S+)', output, flags=re.MULTILINE)
    if len(blocks) < 2:
        return

    for i in range(1, len(blocks), 2):
        filepath = _resolve_filepath(blocks[i].strip(), expected_files)
        if not filepath:
            continue

        block_text = blocks[i + 1]
        searches = re.split(r'^SEARCH\n', block_text, flags=re.MULTILINE)

        for part in searches[1:]:
            search, replace = _parse_block(part)
            if not search:
                continue

            full_path = os.path.join(repo_path, filepath)
            try:
                with open(full_path) as f:
                    file_content = f.read()
            except (OSError, IOError):
                continue

            if search in file_content:
                new_content = file_content.replace(search, replace, 1)
                with open(full_path, "w") as f:
                    f.write(new_content)


def _resolve_filepath(filepath: str, expected_files: list[str]) -> str | None:
    if not filepath.endswith(".go"):
        return None
    if filepath in expected_files:
        return filepath
    for f in expected_files:
        if f.endswith("/" + filepath) or f == filepath:
            return f
    return None


def _parse_block(part: str) -> tuple[str, str]:
    split = re.split(r'\nREPLACE\n', part, maxsplit=1)
    if len(split) != 2:
        return ("", "")
    return split[0].strip("\n"), split[1].strip("\n")
