# cursor-bridge

A small connector that lets Claude (in the Claude desktop app) start Cursor agents on this PC, check on them and read their output. It's how the planner hands work orders to the Cursor builders without anyone copying and pasting.

## What it can and can't do

- It works only inside this repo (`DOOH_REPO`).
- Every agent runs in its own git worktree under `<repo>-worktrees\`, so your own working copy and uncommitted changes are never touched.
- At most 3 agents run at once (`BRIDGE_MAX_JOBS`). Each is stopped after 90 minutes (`BRIDGE_JOB_TIMEOUT_MIN`).
- Logs live in `<repo>\.cursor-bridge\jobs\<job>\output.log`, which git ignores locally.
- Commits are made on this PC with your git identity, and `.githooks/commit-msg` strips AI attribution lines.
- It runs the Cursor CLI with `--force`, so the agent can edit files and run commands inside its worktree. That is how it builds.

## Tools Claude gets

| Tool | What it does |
|---|---|
| `cursor_check` | Health check: Cursor CLI, login, git, running jobs |
| `cursor_start_task` | Start an agent on `tasks/NNN-*.md`, following `.cursor/commands/do-task.md` |
| `cursor_start` | Start an agent with a free-form instruction |
| `cursor_status` | List jobs, or show one job and its latest output |
| `cursor_output` | Read more of a job's output |
| `cursor_stop` | Stop a job |
| `cursor_remove_worktree` | Clean up a finished job's worktree |

## Setup (once)

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\dooh-dsp\tools\cursor-bridge\setup.ps1"
```

The script installs the Cursor CLI if it's missing, finds Python, turns on the commit hook, adds `cursor-bridge` to the Claude desktop config (keeping a backup), logs the CLI in, and runs a health check. Afterwards, fully quit and reopen Claude.

It uses only the Python standard library. There is nothing to `pip install`.

## Settings (environment variables in the Claude config entry)

| Variable | Default |
|---|---|
| `DOOH_REPO` | The repo two folders above this file |
| `CURSOR_AGENT_PATH` | Found automatically |
| `CURSOR_AGENT_FLAGS` | `-p --trust --force --output-format text` |
| `BRIDGE_WORKTREES` | `<repo>-worktrees` |
| `BRIDGE_MAX_JOBS` | `3` |
| `BRIDGE_JOB_TIMEOUT_MIN` | `90` |
