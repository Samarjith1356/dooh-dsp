# How tasks move

Claude plans, Cursor builds, Claude Code reviews, and Sam merges. Each piece of work is one file in this folder, and that file carries the whole history: the brief, what was built, and the review.

## The three commands

| Where | What Sam types | What happens |
|---|---|---|
| claude.ai chat | "Plan the next task" / "Design X" | Claude reads the repo, records any design call in `docs/DECISIONS.md`, writes `tasks/NNN-name.md` and pushes it to `main` |
| Cursor | `/do-task NNN` | Cursor branches, builds, fills in the Builder report, pushes, and opens a PR |
| Claude Code | `/review-task NNN` | The reviewer checks the branch and writes the verdict into the task file |

If the verdict is `CHANGES REQUESTED`, run `/do-task NNN` in Cursor again. It picks up the review notes. If it's `APPROVED`, merge the PR. After merging, tell Claude chat so it can update the status board and plan the next task.

## Running lanes in parallel

Up to three builder agents run at once, one per lane (see `handbook/06-build-team.md`). In Cursor, open the Agents Window, start a new agent, choose **Worktree** so it gets its own copy of the code, and type `/do-task NNN`. Repeat for each lane's task. Each agent stays in its lane's folders and rebases on `main` before pushing. The live board is `handbook/STATUS.md`.

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| `ready` | Brief written, waiting to be built | Claude |
| `building` | Cursor is working on it | Cursor |
| `blocked` | Cursor hit a question the brief doesn't answer (see Open questions) | Cursor |
| `in-review` | Built and pushed, waiting for review | Cursor |
| `changes-requested` | Reviewer found problems | Claude Code |
| `needs-sam` | Reviewer found a question only Sam can answer | Claude Code |
| `approved` | Ready to merge | Claude Code |
| `merged` | Done | Claude, after Sam merges |

`blocked` and `needs-sam` both come back to Sam. Answer in claude.ai chat, Claude records the answer in `DECISIONS.md`, and the task goes back to `ready` or `changes-requested`.

## One-time setup

1. In your local clone, run `git config core.hooksPath .githooks`. This strips AI co-author lines from every commit.
2. In Cursor, go to Settings → Git & PRs (older versions: Agents) → Attribution and turn off commit and PR attribution. The hook is the backstop if an update turns it back on.
3. Optional: install the GitHub CLI (`gh`) and run `gh auth login`, so Cursor and Claude Code can open PRs themselves.
4. Keep using Cursor's local agents (Agents Window, worktrees) for tasks. Cursor's cloud agents commit under their own name, and the hook can't fix that.
5. Set a monthly usage limit in Cursor's settings. Three agents in parallel use roughly three times as much.

## Files

- `TEMPLATE.md` is the shape of every task.
- `BACKLOG.md` is the ordered list of what's next. Claude owns it, and Sam reorders it.
- `NNN-name.md` is one task each, numbered in the order written.
