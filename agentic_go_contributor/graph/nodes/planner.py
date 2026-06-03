from __future__ import annotations

from typing import Any

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.services import LLMService

_SYSTEM = (
    "You are a senior Go engineer. Given an issue and relevant source code, "
    "produce a precise step-by-step implementation plan."
)


class PlanNode:
    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    def __call__(self, state: AgentState) -> dict[str, Any]:
        files = "\n".join(state.get("relevant_files", []))
        tests = "\n".join(state.get("relevant_tests", []))
        context_lines = []
        for path, content in state.get("repository_context", {}).items():
            context_lines.append(f"--- {path} ---\n{content[:3000]}")
        context_text = "\n".join(context_lines)[:15000]

        user = (
            f"Issue summary: {state.get('issue_summary', '')}\n"
            f"Issue type: {state.get('issue_type', '')}\n\n"
            f"Relevant files:\n{files}\n\n"
            f"Relevant tests:\n{tests}\n\n"
            f"File contents:\n{context_text}\n\n"
            "Create a step-by-step implementation plan. Be specific about:\n"
            "- Which functions to modify\n"
            "- What logic to change\n"
            "- What new code to add\n"
            "- What tests to update or add\n\n"
            "Format as a markdown list."
        )

        return {"plan": self._llm.invoke(_SYSTEM, user)}
