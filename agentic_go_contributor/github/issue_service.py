import os

import httpx

from agentic_go_contributor.utils.repo_url import parse_repo_url

GITHUB_API_BASE = "https://api.github.com"


def _build_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "agentic-go-contributor",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_issue(repo_url: str, issue_number: int) -> dict:
    owner, repo = parse_repo_url(repo_url)
    headers = _build_headers()
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"

    with httpx.Client() as client:
        resp = client.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        issue = resp.json()

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
