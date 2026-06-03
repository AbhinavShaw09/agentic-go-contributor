from agentic_go_contributor.graph.state import AgentState
from agentic_go_contributor.repository.code_search import (
    find_files_by_keywords,
    find_related_tests,
    read_file_contents,
)


def explore_repo(state: AgentState) -> dict:
    repo_path = state["local_repo_path"]
    summary = state.get("issue_summary", "")
    constraints = state.get("issue_constraints", [])

    keywords = _extract_keywords(summary, constraints)
    files = find_files_by_keywords(repo_path, keywords)

    if not files:
        from agentic_go_contributor.repository.code_search import list_go_files
        files = list_go_files(repo_path)[:10]

    tests = find_related_tests(repo_path, files)
    context = read_file_contents(repo_path, files + tests)

    return {
        "relevant_files": files,
        "relevant_tests": tests,
        "repository_context": context,
    }


def _extract_keywords(summary: str, constraints: list[str]) -> list[str]:
    import re
    text = summary + " " + " ".join(constraints)

    words = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', text)

    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be",
                 "been", "being", "have", "has", "had", "do", "does",
                 "did", "will", "would", "could", "should", "may",
                 "might", "shall", "can", "need", "to", "of", "in",
                 "for", "on", "with", "at", "by", "from", "as", "into",
                 "through", "during", "before", "after", "above", "below",
                 "between", "out", "off", "over", "under", "again",
                 "further", "then", "once", "here", "there", "when",
                 "where", "why", "how", "all", "each", "every", "both",
                 "few", "more", "most", "other", "some", "such", "no",
                 "nor", "not", "only", "own", "same", "so", "than",
                 "too", "very", "just", "because", "but", "and", "or",
                 "if", "while", "that", "this", "these", "those", "it",
                 "its", "bug", "feature", "refactor", "fix", "add",
                 "implement", "change", "update", "remove", "issue"}

    words = [w for w in words if w.lower() not in stopwords and len(w) > 2]

    return words[:15]
