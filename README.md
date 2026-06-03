# Agentic Go Contributor

A LangGraph-powered CLI agent that resolves GitHub issues in Go repositories end-to-end: analyzes the issue, explores the codebase, generates a fix, validates with Go toolchain, and saves results.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Docker Container                         │
│                                                              │
│  CLI: --repo spf13/cobra --issue 1234                        │
│       │                                                      │
│       ▼                                                      │
│  ┌────────────────────────────────────────────────────┐      │
│  │                 LangGraph Agent                      │      │
│  │                                                      │      │
│  │  fetch_issue ──▶ clone_repo ──▶ analyze_issue        │      │
│  │       │              │               │               │      │
│  │       ▼              ▼               ▼               │      │
│  │  GitHub API      git clone      LLM classify         │      │
│  │       │              │               │               │      │
│  │       └──────────┬───┴───────────────┘               │      │
│  │                  ▼                                   │      │
│  │          explore_repo                                 │      │
│  │               │                                       │      │
│  │               ▼                                       │      │
│  │            planner                                    │      │
│  │               │                                       │      │
│  │               ▼                                       │      │
│  │         coding_agent ──┐                              │      │
│  │               │        │ (retry max 3)                │      │
│  │               ▼        │                              │      │
│  │           validator ────┘                              │      │
│  │               │                                       │      │
│  │               ▼                                       │      │
│  │      ┌────────┴──────────┐                             │      │
│  │      ▼                   ▼                             │      │
│  │  success              failed                           │      │
│  │  (save + exit)    (save + exit)                       │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  LLM: LangChain + OpenRouter   │  Code: Go + git             │
│  Tools: httpx, grep, ripgrep   │  Env: etc/.env              │
└──────────────────────────────────────────────────────────────┘
```

## How It Works

The agent runs 7 sequential nodes in a LangGraph state machine:

| Node | What it does | Tooling |
|------|-------------|---------|
| `fetch_issue` | Fetches issue title, body, comments, labels from GitHub | `httpx` → GitHub REST API |
| `clone_repo` | Clones repo to `/tmp/repos/` (cached, reuses on subsequent runs) | `git clone --depth=1` |
| `analyze_issue` | Classifies as bug/feature/refactor, summarizes expected behavior, extracts constraints | LLM (OpenRouter) |
| `explore_repo` | Greps for relevant symbols, finds related files and test files | `git grep`, file matching |
| `planner` | Generates a step-by-step implementation plan from issue + file context | LLM (OpenRouter) |
| `coding_agent` | Generates SEARCH/REPLACE blocks to modify source code | LLM (OpenRouter) |
| `validator` | Runs `go test ./...` and `go build ./...`; compares against pre-fix baseline to avoid false positives | Go toolchain |

If validation fails, the repair loop feeds errors back to the coding agent (up to 3 attempts).

## Current State

- **Complete 7-node LangGraph pipeline** — runs end-to-end
- **Baseline test comparison** — pre-existing test failures don't trigger false repair loops
- **Dockerized** — single container with Go, Python, git
- **Model-agnostic** — switch models via `OPENROUTER_MODEL` env var
- **Results saved** — each run produces a timestamped output folder
- **Code generation** — uses SEARCH/REPLACE block format (same approach as Aider/Cursor)

### Limitations (V2 candidates)

- Code generation quality depends on the LLM model — larger models produce better patches
- No PR creation yet (output is patch + summary)
- No similar-PR retrieval for context
- No golangci-lint in validation
- Webhook/event-driven mode not implemented

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [OpenRouter](https://openrouter.ai/) API key (free models available)
- GitHub token (for issue fetching)

### Setup

```bash
# 1. Clone the repository
git clone <repo-url> && cd agentic-go-contributor

# 2. Add your API keys
cat > etc/.env << EOF
OPENROUTER_API_KEY=sk-or-v1-...
GITHUB_TOKEN=ghp_...
OPENROUTER_MODEL=openai/gpt-4o-mini
EOF

# 3. Build and run
make docker-build
make docker-run REPO=spf13/cobra ISSUE=1234
```

### Commands

```bash
# Run locally (requires Go + Python deps installed)
make deps
make run REPO=spf13/cobra ISSUE=1234

# Run in Docker
make docker-build
make docker-run REPO=spf13/cobra ISSUE=1234

# Override the model
OPENROUTER_MODEL=openai/gpt-4o make docker-run REPO=spf13/cobra ISSUE=1234

# Clean up
make clean
```

### Output

After each run, results are saved to `results/`:

```
results/
└── spf13_cobra_issue-1234_2026-06-03_17-56-48/
    ├── summary.json        # structured result (repo, issue, type, status)
    ├── plan.md             # LLM-generated implementation plan
    ├── patch.diff          # git diff of code changes
    └── test_results.txt    # validation output (if tests failed)
```

Console output:

```
✓ Issue analyzed (bug: nil pointer dereference on Execute)
✓ Repository explored (3 files, 2 tests)
✓ Plan generated
✓ Code modified
✓ Tests passed

📁 Results saved to: results/spf13_cobra_issue-1234_2026-06-03_17-56-48/
```

## Project Structure

```
agentic_go_contributor/
├── cli.py                   # click CLI entry point
├── llm.py                   # LangChain + OpenRouter helper
├── graph/
│   ├── state.py             # AgentState TypedDict
│   ├── graph.py             # LangGraph wiring + repair loop
│   └── nodes/
│       ├── fetch_issue.py   # GitHub API → issue details
│       ├── clone_repo.py    # git clone (cached) + baseline tests
│       ├── issue_analyzer.py# LLM classify + summarize
│       ├── repo_explorer.py # grep for relevant files/tests
│       ├── planner.py       # LLM step-by-step plan
│       ├── coding_agent.py  # SEARCH/REPLACE code generation
│       └── validator.py     # go test + go build
├── github/
│   └── issue_service.py     # httpx → GitHub REST API
├── repository/
│   ├── clone.py             # git clone with caching
│   └── code_search.py       # grep/ripgrep wrappers
└── prompts/
    ├── issue_analyzer.md
    ├── planner.md
    └── coding_agent.md
```

## Config

| Env var | Default | Description |
|---------|---------|-------------|
| `OPENROUTER_API_KEY` | (required) | OpenRouter API key |
| `GITHUB_TOKEN` | (required) | GitHub personal access token |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model for all LLM calls |
| `OPENROUTER_MAX_TOKENS` | `1024` | Max tokens per LLM response |
