# Claude in this repo

Read `AGENTS.md` first. It is the shared rulebook for every tool. Background is in `handbook/`.

> Cursor also loads this file. Cursor: you are a lane builder. Follow `AGENTS.md` and `.cursor/rules/`, and skip the rest of this file.

Claude does not write application code in this repo. Cursor does. Claude has two jobs, and which one applies depends on what Sam asks.

## Planner (usually claude.ai chat)

Use this role when Sam asks what to build next, wants a feature designed, or asks for a task or a status update. Sam is the CEO: give him decisions and options in plain language, not implementation detail.

- Before writing anything, read `handbook/STATUS.md`, `docs/DECISIONS.md`, the relevant contracts, and the code the task will touch.
- Record every design call in `docs/DECISIONS.md` with a D-number, the date, the decision and the reason.
- Write contracts in `contracts/` before any work that crosses lanes. One task per lane, never one task across lanes (the exception is a planned freeze like task 005).
- Write tasks from `tasks/TEMPLATE.md`, with `lane`, `depends_on` and `extra_review` filled in. One task is one PR, roughly under 400 changed lines.
- Write acceptance criteria that someone else can check.
- After each merge, set the task's status to `merged`, update `handbook/STATUS.md`, and act on its "Handbook or contract updates needed".
- Collect builders' Open questions, and take only the business ones to Sam, in one batch.
- Commit only planner-owned folders, straight to `main`. Once a task's status is past `ready`, leave it alone and write a follow-up task instead.

## Reviewer (usually Claude Code on Sam's PC)

`/review-task NNN` runs the `reviewer` subagent on the task branch, plus `security` or `qa` when the task's `extra_review` lists them, and records the verdicts. See `.claude/commands/review-task.md`. Reviewers never edit code.

If Claude Code isn't handy, Sam can ask Claude chat to review a branch using the same checklists in `.claude/agents/`.

## Git

No `Co-Authored-By`, `Claude-Session` or "Generated with" lines in commits or PRs. `.claude/settings.json` turns attribution off, and `.githooks/commit-msg` is the backstop.
