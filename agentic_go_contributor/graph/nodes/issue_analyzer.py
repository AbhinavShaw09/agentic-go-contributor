from __future__ import annotations

import json
import re
from typing import Any

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import LLMService

_SYSTEM = "You analyze GitHub issues and output JSON only."


class AnalyzeIssueNode:
    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    def __call__(self, state: AgentState) -> dict[str, Any]:
        issue = state["issue"]
        title = issue.get("title", "")
        body = issue.get("body", "")
        labels = ", ".join(issue.get("labels", []))
        comments_lines = [
            f"{c['author']}: {c['body']}" for c in issue.get("comments", [])
        ]
        comments = "\n".join(comments_lines) or "None"

        user = (
            "Classify this GitHub issue.\n\n"
            f"Title: {title}\n"
            f"Body: {body}\n"
            f"Labels: {labels}\n\n"
            f"Comments: {comments}\n\n"
            'Output valid JSON with these fields:\n'
            '- "issue_type": "bug", "feature", or "refactor"\n'
            '- "summary": one-sentence summary of expected behavior\n'
            '- "constraints": list of specific requirements or constraints\n\n'
            "JSON:"
        )

        text = self._llm.invoke(_SYSTEM, user)
        parsed = _parse_json(text)

        return {
            "issue_type": parsed.get("issue_type", "bug"),
            "issue_summary": parsed.get("summary", ""),
            "issue_constraints": parsed.get("constraints", []),
        }


def _parse_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    issue_type = "bug"
    if "feature" in text.lower():
        issue_type = "feature"
    elif "refactor" in text.lower():
        issue_type = "refactor"

    summary = text.strip().split("\n")[0] if text.strip() else ""
    return {"issue_type": issue_type, "summary": summary, "constraints": []}
