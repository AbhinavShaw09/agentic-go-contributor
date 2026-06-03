import time

from langchain_core.messages import HumanMessage, SystemMessage

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.llm import get_llm


def plan(state: AgentState) -> dict:
    llm = get_llm()

    files = "\n".join(state.get("relevant_files", []))
    tests = "\n".join(state.get("relevant_tests", []))
    context_lines = []
    for path, content in state.get("repository_context", {}).items():
        context_lines.append("--- " + path + " ---\n" + content[:3000])
    context_text = "\n".join(context_lines)[:15000]

    system = (
        "You are a senior Go engineer. Given an issue and relevant source code, "
        "produce a precise step-by-step implementation plan."
    )

    user = (
        "Issue summary: " + state.get("issue_summary", "") + "\n"
        "Issue type: " + state.get("issue_type", "") + "\n\n"
        "Relevant files:\n" + files + "\n\n"
        "Relevant tests:\n" + tests + "\n\n"
        "File contents:\n" + context_text + "\n\n"
        "Create a step-by-step implementation plan. Be specific about:\n"
        "- Which functions to modify\n"
        "- What logic to change\n"
        "- What new code to add\n"
        "- What tests to update or add\n\n"
        "Format as a markdown list."
    )

    for retry in range(3):
        try:
            result = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            return {"plan": result.content}
        except Exception as e:
            if retry == 2:
                raise
            err = str(e)
            if "429" in err or "503" in err:
                time.sleep(2 ** retry * 5)
                continue
            time.sleep(2)
