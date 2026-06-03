# Agentic Go Contributor — V1 Plan

## Overview

A CLI tool that resolves GitHub issues in Go repositories using a LangGraph-powered agent pipeline. It analyzes the issue, explores the repository, generates a code patch via OpenCode, validates with Go toolchain, and reports results.

## Stack

| Concern              | Choice                        |
| -------------------- | ----------------------------- |
| Agent orchestration  | **LangGraph**                 |
| LLM calls            | **LangChain + OpenRouter**    |
| Code modification    | **OpenCode** (subprocess)     |
| Runtime              | **Docker** (full isolation)   |
| CLI                  | **click**                     |
| Project management   | **Poetry**                    |
| GitHub API           | **httpx** (REST API)          |
| Validation           | `go test ./...` + `go build ./...` |

## Folder Structure

```
agentic-go-contributor/
├── Dockerfile
├── .dockerignore
├── .env.example
├── pyproject.toml
├── agentic_go_contributor/
│   ├── __init__.py
│   ├── cli.py                         # click CLI entry point
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── graph.py                   # LangGraph wiring + conditional edges
│   │   ├── state.py                   # AgentState TypedDict
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── fetch_issue.py         # GitHub API → issue details
│   │       ├── clone_repo.py          # git clone (cached)
│   │       ├── issue_analyzer.py      # LLM: classify + summarize
│   │       ├── repo_explorer.py       # grep/ripgrep for relevant files
│   │       ├── planner.py             # LLM: step-by-step plan
│   │       ├── coding_agent.py        # OpenCode subprocess → patch
│   │       └── validator.py           # go test + go build
│   ├── github/
│   │   ├── __init__.py
│   │   └── issue_service.py           # httpx calls to GitHub REST API
│   ├── repository/
│   │   ├── __init__.py
│   │   ├── clone.py                   # git clone with caching
│   │   └── code_search.py             # grep/ripgrep wrappers
│   └── prompts/
│       ├── issue_analyzer.md
│       ├── planner.md
│       └── coding_agent.md
```

## LangGraph State

```python
class AgentState(TypedDict):
    repo_url: str
    issue_number: int
    local_repo_path: str

    issue: dict

    issue_type: str                     # bug | feature | refactor
    issue_summary: str
    issue_constraints: list[str]

    relevant_files: list[str]
    relevant_tests: list[str]
    repository_context: dict

    plan: str

    patch: str

    validation_attempts: int
    validation_success: bool
    validation_errors: list[str]
```

## Node Details

### 1. `fetch_issue`

| Aspect   | Detail                                      |
| -------- | ------------------------------------------- |
| Input    | `repo_url`, `issue_number`                  |
| Output   | `issue` dict (title, body, comments, labels) |
| Tool     | `httpx` → `GET /repos/{owner}/{repo}/issues/{number}` |
| LLM?     | No                                          |

### 2. `clone_repo`

| Aspect   | Detail                                       |
| -------- | -------------------------------------------- |
| Input    | `repo_url`                                   |
| Output   | `local_repo_path`                            |
| Tool     | `git clone` (skip if already cached at path) |
| LLM?     | No                                           |

### 3. `issue_analyzer`

| Aspect   | Detail                                                  |
| -------- | ------------------------------------------------------- |
| Input    | `issue`                                                 |
| Output   | `issue_type`, `issue_summary`, `issue_constraints`      |
| Tool     | LangChain + OpenRouter with `prompts/issue_analyzer.md` |
| LLM?     | Yes — classify bug/feature/refactor, summarize          |

**Prompt structure:**

```
Classify this GitHub issue as "bug", "feature", or "refactor".
Summarize the expected behavior.
Extract any specific constraints or requirements.

Issue title: {title}
Issue body: {body}
Labels: {labels}
```

### 4. `repo_explorer`

| Aspect   | Detail                                                |
| -------- | ----------------------------------------------------- |
| Input    | `issue_summary`, `local_repo_path`                    |
| Output   | `relevant_files`, `relevant_tests`, `repository_context` |
| Tools    | `grep`, `ripgrep`, `git ls-files`                     |
| LLM?     | No                                                    |

Logic:
- Parse issue summary for keywords (function names, error messages, feature names)
- Run grep for those keywords across the repo
- Identify related test files (same directory, `_test.go` suffix)
- Read relevant file contents into `repository_context`

### 5. `planner`

| Aspect   | Detail                                            |
| -------- | ------------------------------------------------- |
| Input    | `issue_summary`, `relevant_files`, `repository_context` |
| Output   | `plan` (markdown step list)                       |
| Tool     | LangChain + OpenRouter with `prompts/planner.md`  |
| LLM?     | Yes                                               |

**Prompt structure:**

```
Issue summary: {summary}
Relevant files: {files}
File contents: {context}

Create a step-by-step implementation plan.
Be specific about which functions to modify and what to change.
```

### 6. `coding_agent`

| Aspect   | Detail                                                       |
| -------- | ------------------------------------------------------------ |
| Input    | `plan`, `relevant_files`, `local_repo_path`                  |
| Output   | `patch`                                                      |
| Tool     | OpenCode subprocess + `git diff`                             |
| LLM?     | Via OpenCode                                                 |

Logic:

```python
task = f"""Issue: {issue_summary}
Type: {issue_type}
Plan:
{plan}

Relevant files: {relevant_files}

File contents:
{repository_context}

Implement the changes described in the plan above.
After making changes, output a summary.
"""
Path(repo_path, "task.md").write_text(task)
subprocess.run(["opencode", "-p", "task.md"], cwd=repo_path, check=True)
result = subprocess.run(["git", "diff"], cwd=repo_path, capture_output=True, text=True)
patch = result.stdout
```

On retry (validation failure), append error context to the task file and re-run.

### 7. `validator`

| Aspect   | Detail                                       |
| -------- | -------------------------------------------- |
| Input    | `local_repo_path`                            |
| Output   | `validation_success`, `validation_errors`    |
| Tools    | `go test ./...`, `go build ./...`            |
| LLM?     | No                                           |

```python
result = subprocess.run(["go", "test", "./..."], cwd=repo_path, capture_output=True, text=True)
build = subprocess.run(["go", "build", "./..."], cwd=repo_path, capture_output=True, text=True)
success = result.returncode == 0 and build.returncode == 0
```

## Graph Wiring

```
fetch_issue → clone_repo → analyze_issue → explore_repo → planner → code → validate
                                                                                │
                                                         ┌──────────────────────┘
                                                         ▼
                                                  success? ──yes──▶ END
                                                         │ no + attempts < 3
                                                         ▼
                                                       code (retry)
                                                         │
                                                         ▼ (attempts >= 3)
                                                       END
```

## CLI

```bash
docker run --rm \
  -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  agentic-go-contributor \
  --repo spf13/cobra \
  --issue 1234
```

**Output:**

```
✓ Issue analyzed (bug: nil pointer dereference on Execute)
✓ Repository explored (3 files, 2 tests)
✓ Plan generated
✓ Code modified
✓ Tests passed

--- Patch ---
diff --git a/command.go b/command.go
...

--- Summary ---
Issue: #1234
Type: bug
Files changed: command.go, command_test.go
Tests: 12 passed, 0 failed
```

## Dockerfile

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y golang-go nodejs npm git && rm -rf /var/lib/apt/lists/*
RUN npm install -g @opencode/cli
RUN go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
WORKDIR /app
COPY pyproject.toml .
RUN pip install poetry && poetry install --no-root
COPY . .
ENTRYPOINT ["poetry", "run", "python", "-m", "agentic_go_contributor.cli"]
```

## Dependencies (`pyproject.toml`)

```toml
[tool.poetry.dependencies]
python = "^3.11"
langgraph = "^0.2"
langchain = "^0.3"
langchain-openai = "^0.2"
click = "^8.1"
httpx = "^0.27"
pyyaml = "^6.0"
python-dotenv = "^1.0"

[tool.poetry.scripts]
agentic-go-contributor = "agentic_go_contributor.cli:main"
```

## Implementation Order

| #  | Step                    | Files                                                | Effort |
| -- | ----------------------- | ---------------------------------------------------- | ------ |
| 1  | Project skeleton        | `Dockerfile`, `pyproject.toml`, `.env.example`, `.dockerignore` | 30min  |
| 2  | CLI entry point         | `cli.py`                                             | 30min  |
| 3  | GitHub issue service    | `github/issue_service.py`                            | 1hr    |
| 4  | Repo clone + cache      | `repository/clone.py`, `repository/code_search.py`   | 1.5hr  |
| 5  | LangGraph state + graph | `graph/state.py`, `graph/graph.py`                   | 1hr    |
| 6  | Issue analyzer node     | `graph/nodes/issue_analyzer.py`, `prompts/issue_analyzer.md` | 1.5hr  |
| 7  | Repo explorer node      | `graph/nodes/repo_explorer.py`                       | 1hr    |
| 8  | Planner node            | `graph/nodes/planner.py`, `prompts/planner.md`       | 1hr    |
| 9  | Coding agent node       | `graph/nodes/coding_agent.py`, `prompts/coding_agent.md` | 1.5hr  |
| 10 | Validator node          | `graph/nodes/validator.py`                           | 1hr    |
| 11 | Wire repair loop        | Update `graph.py` (conditional edge)                 | 30min  |
| 12 | End-to-end test         | Run against a real Go repo issue                     | 2hr    |

**Total estimated effort: ~12-14 hours**

## Edge Cases & Design Decisions

- **Repo caching**: Clone to `/tmp/repos/{owner}/{repo}`. Skip clone if directory exists.
- **OpenCode non-interactive**: Uses `-p` flag for prompt. Fallback to piping via stdin if unsupported.
- **Repair loop**: Feed validation errors + original plan + generated patch back to OpenCode. Max 3 attempts.
- **Network**: Docker container needs internet for GitHub API and OpenRouter API calls.
- **Large repos**: Limit matched files to top 10 most relevant.
- **No golangci-lint in V1**: Skip lint, add in V2.

## Future (V2+)

- Similar PR retrieval (GitHub search for merged PRs matching the issue)
- golangci-lint validation
- Automatic PR creation via `gh pr create`
- Webhook-based trigger (GitHub App)
- Multi-language support
