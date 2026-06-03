# Agentic Go Contributor

A LangGraph-powered CLI agent that resolves GitHub issues in Go repositories end-to-end: analyzes the issue, explores the codebase, generates a fix, validates with Go toolchain, and saves results.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Container                        │
│                                                                 │
│  CLI: --repo spf13/cobra --issue 1234 --run-id abc123           │
│       │                                                         │
│       ▼                                                         │
│  ┌───────────────────────────────────────────────────────┐      │
│  │                 LangGraph Agent                       │      │
│  │                                                       │      │
│  │  fetch_issue ──▶ clone_repo ──▶ analyze_issue         │      │
│  │       │              │               │                │      │
│  │       ▼              ▼               ▼                │      │
│  │  GitHub API      git clone      LLM classify          │      │
│  │       │              │               │                │      │
│  │       └──────────┬───┴───────────────┘                │      │
│  │                  ▼                                    │      │
│  │          explore_repo                                 │      │
│  │               │                                       │      │
│  │               ▼                                       │      │
│  │            planner                                    │      │
│  │               │                                       │      │
│  │               ▼                                       │      │
│  │         coding_agent ──┐                              │      │
│  │               │        │ (retry max 3)                │      │
│  │               ▼        │                              │      │
│  │           validator ────┘                             │      │
│  │               │                                       │      │
│  │               ▼                                       │      │
│  │        human_review ────┐                             │      │
│  │          │              │                             │      │
│  │    ┌─────┴──────┐      │                              │      │
│  │    ▼            ▼      │                              │      │
│  │ approved    rejected ──┘                              │      │
│  │ (save +     (retry max 3,                             │      │
│  │  exit)       else exit)                               │      │
│  └───────────────────────────────────────────────────────┘      │
│                      │                              ▲           │
│                      ▼ data/runs/<run_id>/          │           │
│              ┌───────────────────────┐              │           │
│              │  review.json          │──────────────┘           │
│              │  decision.json        │  (poll every 5s)         │
│              │  status.json          │                          │
│              │  summary.json         │                          │
│              └───────────────────────┘                          │
│                      │                                          │
│                      ▼ HTTP                                     │
│  ┌────────────────────────────────────────┐                     │
│  │       Next.js Dashboard (port 3000)      │                   │
│  │                                          │                   │
│  │  /          — list runs + start form     │                   │
│  │  /review/abc123 — approve / reject       │                   │
│  └──────────────────────────────────────────┘                   │
│                                                                 │
│  LLM: LangChain + OpenRouter   │  IPC: File-based (data/runs/)  │
│  Tools: httpx, grep, ripgrep   │  Env: etc/.env                 │
└─────────────────────────────────────────────────────────────────┘
```

## How It Works

The agent runs 8 sequential nodes in a LangGraph state machine:

| Node | What it does | Tooling |
|------|-------------|---------|
| `fetch_issue` | Fetches issue title, body, comments, labels from GitHub | `httpx` → GitHub REST API |
| `clone_repo` | Clones repo to `/tmp/repos/` (cached, reuses on subsequent runs) | `git clone --depth=1` |
| `analyze_issue` | Classifies as bug/feature/refactor, summarizes expected behavior, extracts constraints | LLM (OpenRouter) |
| `explore_repo` | Greps for relevant symbols, finds related files and test files | `git grep`, file matching |
| `planner` | Generates a step-by-step implementation plan from issue + file context | LLM (OpenRouter) |
| `coding_agent` | Generates SEARCH/REPLACE blocks to modify source code | LLM (OpenRouter) |
| `validator` | Runs `go test ./...` and `go build ./...`; compares against pre-fix baseline to avoid false positives | Go toolchain |
| `human_review` | Writes patch + plan to `data/runs/<id>/review.json`, polls for `decision.json` | File-based IPC |

If validation fails, the repair loop feeds errors back to the coding agent (up to 3 attempts). After validation passes (or max attempts), the agent writes a review request to a shared `data/` directory and waits. The Next.js dashboard reads it and presents the patch for approval. The human's decision is written as `decision.json`, which the agent picks up (polling every 5s).

## Current State

- **Complete 8-node LangGraph pipeline** — runs end-to-end
- **Baseline test comparison** — pre-existing test failures don't trigger false repair loops
- **Dockerized** — single container with Go, Python, git
- **Model-agnostic** — switch models via `OPENROUTER_MODEL` env var
- **Results saved** — each run produces a timestamped output folder
- **Code generation** — uses SEARCH/REPLACE block format (same approach as Aider/Cursor)
- **Dashboard with human-in-the-loop** — CLI writes to `data/runs/`, Next.js dashboard reads + displays, decision flows back via file

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

# 3. Start the dashboard (terminal 1)
make dashboard

# 4. Run the agent (terminal 2)
make docker-build
make docker-run REPO=spf13/cobra ISSUE=1234

# 5. Open http://localhost:3000/review/<run-id> when prompted
```

### Commands

```bash
# Run locally (requires Go + Python deps installed)
make deps
make run REPO=spf13/cobra ISSUE=1234

# Run in Docker
make docker-build
make docker-run REPO=spf13/cobra ISSUE=1234

# Start the dashboard (runs on http://localhost:3000)
make dashboard-deps
make dashboard

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
🚀 Resolving issue #1234 in spf13/cobra...
   Run ID: abc12345
   Dashboard: http://localhost:3000/review/abc12345

✓ Issue analyzed (bug: nil pointer dereference on Execute)
✓ Repository explored (3 files, 2 tests)
✓ Plan generated
✓ Code modified
✓ Tests passed

  📋 Patch ready for review!
  🔗 Open: http://localhost:3000/review/abc12345
  ⏳ Waiting for decision (up to 30 min)...

  ✅ Patch approved via dashboard

--- Patch ---
...

📁 Results saved to: results/spf13_cobra_issue-1234_2026-06-03_17-56-48/

🔗 Dashboard: http://localhost:3000/review/abc12345
```

## Project Structure

```
agentic_go_contributor/
├── cli.py                   # click CLI entry point
├── services.py              # Service classes + DI container
├── graph/
│   ├── base.py              # GraphNode protocol
│   ├── state.py             # AgentState TypedDict
│   ├── graph.py             # LangGraph wiring + repair loop
│   └── nodes/
│       ├── fetch_issue.py   # GitHub API → issue details
│       ├── clone_repo.py    # git clone (cached) + baseline tests
│       ├── issue_analyzer.py# LLM classify + summarize
│       ├── repo_explorer.py # grep for relevant files/tests
│       ├── planner.py       # LLM step-by-step plan
│       ├── coding_agent.py  # SEARCH/REPLACE code generation
│       ├── validator.py     # go test + go build
│       └── human_review.py  # File-based IPC review
├── github/
│   └── issue_service.py     # (replaced by GitHubService)
├── repository/
│   ├── clone.py             # git clone with caching
│   └── code_search.py       # grep/ripgrep wrappers
└── utils/
    ├── constants.py          # Shared timeouts, retry limits
    └── repo_url.py           # parse_repo_url() helper

dashboard/                        # Next.js review dashboard
├── package.json
├── app/
│   ├── page.tsx                  # Dashboard — list runs
│   ├── review/[runId]/page.tsx   # Review page — approve / reject
│   └── api/runs/[runId]/route.ts # API — read run + write decision
└── lib/runs.ts                   # Filesystem read/write helpers

data/                             # Shared IPC directory
└── runs/<run_id>/
    ├── status.json               # running / pending_review / approved / completed
    ├── review.json               # patch + plan + errors (agent → dashboard)
    ├── decision.json             # approved + feedback (dashboard → agent)
    ├── summary.json              # final result
    ├── plan.md / patch.diff      # artifacts
    └── test_results.txt          # validation output
```

## Config

| Env var | Default | Description |
|---------|---------|-------------|
| `OPENROUTER_API_KEY` | (required) | OpenRouter API key |
| `GITHUB_TOKEN` | (required) | GitHub personal access token |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model for all LLM calls |
| `OPENROUTER_MAX_TOKENS` | `1024` | Max tokens per LLM response |
| `DASHBOARD_URL` | `http://localhost:3000` | URL printed by CLI for review link |
