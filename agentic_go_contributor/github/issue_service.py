import os
import httpx


GITHUB_API_BASE = "https://api.github.com"


def fetch_issue(repo_url: str, issue_number: int) -> dict:
    owner, repo = _parse_repo_url(repo_url)
    token = os.environ.get("GITHUB_TOKEN", "")

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "agentic-go-contributor",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"

    with httpx.Client() as client:
        resp = client.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        issue = resp.json()

        comments_url = issue.get("comments_url", "")
        if comments_url:
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


def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    repo_url = repo_url.rstrip("/")
    if repo_url.startswith("http"):
        parts = repo_url.rstrip(".git").split("/")
        return parts[-2], parts[-1]
    if repo_url.startswith("git@"):
        parts = repo_url.rstrip(".git").split(":")[-1].split("/")
        return parts[0], parts[1]
    if "/" in repo_url:
        parts = repo_url.split("/")
        return parts[0], parts[1]
    raise ValueError(f"Unable to parse repo URL: {repo_url}")
