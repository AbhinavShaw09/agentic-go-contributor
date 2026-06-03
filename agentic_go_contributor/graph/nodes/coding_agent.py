import os
import re
import subprocess
import time

from langchain_core.messages import HumanMessage, SystemMessage

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.llm import get_llm
from agentic_go_contributor.repository.clone import get_diff, reset_hard


CODE_MODEL = "openai/gpt-4o-mini"


def code(state: AgentState) -> dict:
    repo_path = state["local_repo_path"]
    summary = state.get("issue_summary", "")
    issue_type = state.get("issue_type", "")
    plan_text = state.get("plan", "")
    files = state.get("relevant_files", [])
    context = state.get("repository_context", {})
    errors = state.get("validation_errors", [])
    attempt = state.get("validation_attempts", 0)

    reset_hard(repo_path)

    targets = [f for f in files if not f.startswith("go.")][:2]
    context_text = _build_context(targets, context)
    errors_text = _build_errors(errors, attempt)

    llm = get_llm(CODE_MODEL)

    system = (
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

    user = (
        "Issue: " + issue_type + " - " + summary + "\n\n"
        "Plan:\n" + plan_text + "\n\n"
        "Files to modify and their current contents:\n" + context_text + "\n\n"
        "Previous errors to fix:\n" + errors_text + "\n\n"
        "Output SEARCH/REPLACE blocks for each change needed. "
        "Make sure SEARCH text matches the current file content exactly."
    )

    output = ""
    for retry in range(3):
        try:
            result = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            output = result.content
            if output.strip():
                break
        except Exception as e:
            err = str(e)
            if "429" in err or "503" in err:
                time.sleep(2 ** retry * 5)
                continue
            if retry == 2:
                raise
            time.sleep(2)

    _apply_blocks(repo_path, output, targets, context)

    patch = get_diff(repo_path)
    return {"patch": patch}


def _build_context(files: list[str], context: dict) -> str:
    max_chars = 15000
    lines = []
    remaining = max_chars
    for f in files:
        content = context.get(f, "")
        if content:
            chunk = content[:remaining]
            lines.append("--- " + f)
            lines.append(chunk)
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
    return "\n".join("- " + e[:500] for e in errors)


def _apply_blocks(repo_path: str, output: str, expected_files: list[str], originals: dict) -> None:
    blocks = re.split(r'^FILE:\s*(\S+)', output, flags=re.MULTILINE)
    if len(blocks) < 2:
        return

    for i in range(1, len(blocks), 2):
        filepath = blocks[i].strip()
        if not filepath.endswith(".go"):
            continue
        if filepath not in expected_files:
            matched = [f for f in expected_files if f.endswith("/" + filepath) or f == filepath]
            if not matched:
                continue
            filepath = matched[0]

        block_text = blocks[i + 1]
        searches = re.split(r'^SEARCH\n', block_text, flags=re.MULTILINE)

        for part in searches[1:]:
            parts = re.split(r'\nREPLACE\n', part, maxsplit=1)
            if len(parts) != 2:
                continue
            search = parts[0].strip("\n")
            replace = parts[1].strip("\n")

            if not search:
                continue

            full_path = os.path.join(repo_path, filepath)
            try:
                with open(full_path, "r") as f:
                    file_content = f.read()
            except (OSError, IOError):
                continue

            if search in file_content:
                new_content = file_content.replace(search, replace, 1)
                with open(full_path, "w") as f:
                    f.write(new_content)
