def parse_repo_url(repo_url: str) -> tuple[str, str]:
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
