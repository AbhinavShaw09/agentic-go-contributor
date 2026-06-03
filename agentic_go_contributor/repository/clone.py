import subprocess
import tempfile
from pathlib import Path

from agentic_go_contributor.utils.repo_url import parse_repo_url

REPOS_CACHE = Path(tempfile.gettempdir()) / "repos"


def clone_repo(repo_url: str) -> str:
    owner, repo = parse_repo_url(repo_url)
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


def reset_hard(repo_path: str) -> None:
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_path, check=True)
    subprocess.run(["git", "clean", "-fd"], cwd=repo_path, check=True)
