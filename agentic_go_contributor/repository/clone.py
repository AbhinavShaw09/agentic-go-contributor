import os
import subprocess
import tempfile
from pathlib import Path


REPOS_CACHE = Path(tempfile.gettempdir()) / "repos"


def clone_repo(repo_url: str) -> str:
    owner, repo = _parse_repo(repo_url)
    repo_path = REPOS_CACHE / owner / repo

    if repo_path.exists():
        _git_pull(repo_path)
        return str(repo_path)

    repo_path.mkdir(parents=True, exist_ok=True)
    clone_url = f"https://github.com/{owner}/{repo}.git"

    subprocess.run(
        ["git", "clone", "--depth=1", clone_url, str(repo_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    return str(repo_path)


def _parse_repo(repo_url: str) -> tuple[str, str]:
    repo_url = repo_url.rstrip("/")
    if repo_url.startswith("http"):
        parts = repo_url.rstrip(".git").split("/")
        return parts[-2], parts[-1]
    if "/" in repo_url:
        parts = repo_url.split("/")
        return parts[0], parts[1]
    raise ValueError(f"Unable to parse repo URL: {repo_url}")


def _git_pull(repo_path: Path) -> None:
    try:
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        pass


def get_diff(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "diff"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.stdout


def stage_all_and_commit(repo_path: str, message: str = "wip") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )


def reset_hard(repo_path: str) -> None:
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_path, check=True)
    subprocess.run(["git", "clean", "-fd"], cwd=repo_path, check=True)
