import subprocess
from pathlib import Path


def find_files_by_keywords(repo_path: str, keywords: list[str]) -> list[str]:
    matched = set()

    for keyword in keywords:
        if not keyword.strip():
            continue
        try:
            result = subprocess.run(
                ["git", "grep", "-il", keyword, "--", "*.go"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                for f in result.stdout.strip().split("\n"):
                    if f.endswith(".go") and not f.endswith("_test.go"):
                        matched.add(f)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            continue

    return sorted(matched)


def find_related_tests(repo_path: str, source_files: list[str]) -> list[str]:
    tests = set()

    for src_file in source_files:
        src_path = Path(src_file)
        test_file = src_path.parent / f"{src_path.stem}_test.go"
        candidate = str(test_file)
        if Path(repo_path, candidate).exists():
            tests.add(candidate)

        dir_tests = list(Path(repo_path, src_path.parent).glob("*_test.go"))
        for t in dir_tests:
            tests.add(str(t.relative_to(repo_path)))

    return sorted(tests)


def read_file_contents(repo_path: str, files: list[str]) -> dict[str, str]:
    contents = {}
    for f in files:
        path = Path(repo_path) / f
        if path.exists():
            try:
                contents[f] = path.read_text()
            except Exception:
                contents[f] = ""
    return contents


def list_go_files(repo_path: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "*.go"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().split("\n") if f]
