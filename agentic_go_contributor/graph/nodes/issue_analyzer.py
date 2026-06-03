import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.llm import get_llm


def analyze_issue(state: AgentState) -> dict:
    issue = state["issue"]
    llm = get_llm()

    title = issue.get("title", "")
    body = issue.get("body", "")
    labels = ", ".join(issue.get("labels", []))
    comments = "\n".join(c["author"] + ": " + c["body"] for c in issue.get("comments", [])) or "None"

    system = "You analyze GitHub issues and output JSON only."
    user = (
        "Classify this GitHub issue.\n\n"
        "Title: " + title + "\n"
        "Body: " + body + "\n"
        "Labels: " + labels + "\n\n"
        "Comments: " + comments + "\n\n"
        'Output valid JSON with these fields:\n'
        '- "issue_type": "bug", "feature", or "refactor"\n'
        '- "summary": one-sentence summary of expected behavior\n'
        '- "constraints": list of specific requirements or constraints\n\n'
        "JSON:"
    )

    for retry in range(3):
        try:
            result = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            text = result.content
            if text.strip():
                break
        except Exception as e:
            if retry == 2:
                raise
            err = str(e)
            if "429" in err or "503" in err:
                time.sleep(2 ** retry * 5)
                continue
            time.sleep(2)

    parsed = _parse_json(text)

    return {
        "issue_type": parsed.get("issue_type", "bug"),
        "issue_summary": parsed.get("summary", ""),
        "issue_constraints": parsed.get("constraints", []),
    }


def _parse_json(text: str) -> dict:
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
