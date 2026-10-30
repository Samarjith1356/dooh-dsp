# Working on dooh-dsp

Every AI coding tool that opens this repo reads this file. Cursor loads it automatically, and Claude reads it through `CLAUDE.md`.

**New here? Read `handbook/README.md` first.** It takes ten minutes and covers the mission, how DOOH works, the architecture, the Irish ad rules, the roadmap and the team.

## Who does what

| Who | Job | Writes to |
|---|---|---|
| Sam (CEO) | Priorities, business decisions, merges | Anything |
| Claude, the planner (claude.ai chat) | Specs, contracts, task briefs, decisions, the handbook, status | `contracts/`, `handbook/`, `docs/DECISIONS.md`, `tasks/` (on `main`) |
| Cursor builders, one per lane | Build one task at a time in their own lane | Their lane's folders, plus files the task grants |
| Claude Code (on Sam's PC) | Reviews every branch before merge (`reviewer`, plus `security` / `qa` when a task asks) | The task's Review section only |

The lanes are Trading, Platform, Experience and Agents. Who owns which folders is in `handbook/06-build-team.md`. Builders don't edit outside their lane unless the task grants a file by name.

Grok is not part of the build loop. The product's control-plane agents still call the xAI API at runtime, but that is product code.

The `agents/` folder is product code: the runtime agents behind Sam's Desk and the future Central Brain. It is not the coding agents described here.

## The loop

1. The planner writes `tasks/NNN-short-name.md` with status `ready`.
2. In Cursor (Agents Window, one worktree per agent), Sam runs `/do-task NNN`. The builder creates the branch `task/NNN-short-name`, builds, fills in the Builder report, sets status `in-review`, rebases on `main`, and pushes.
3. In Claude Code, Sam runs `/review-task NNN`. The verdict goes into the task file: `APPROVED`, `CHANGES REQUESTED` or `NEEDS SAM`.
4. If changes are requested, go back to step 2.
5. If approved, Sam merges. The planner updates `handbook/STATUS.md` and copies the task's Log entries into `docs/build-log.csv`.

## Rules for anyone writing code here

- **Bid path golden rule.** HTTP parse -> in-memory match -> bid/no-bid -> async log. Never on that path: LLM/LangGraph, Postgres, ClickHouse, S3/MinIO, compile.
- **Money.** Integer micros (1 EUR = 1,000,000). Billable impressions include `imp.qty.multiplier` once. Spend is booked only on billing notices (`contracts/events.md`).
- **Contracts.** Build against `contracts/`. If a contract is wrong, stop and ask. Never change one yourself.
- **Scope.** Build what the task asks. Note anything else under "Found along the way".
- **Learn from the log.** Before you start, read the rows in `docs/build-log.csv` for your area, mistakes and lessons first (`docs/build-log.md` shows how).
- **Business logic needs Sam.** Build only the business rules the task states and Sam approved (D-014). If you need a rule about money, pricing, customers, approvals or compliance that the task doesn't state, set status `blocked` and ask. Build only tasks from `tasks/BACKLOG.md`: no extras.
- **No hidden decisions.** If a product or architecture question is open, write it under Open questions, set status `blocked`, and stop.
- **Honest numbers.** Never show placeholder, sampled or demo data as live totals. Demo mode is labelled on screen.
- **Tests.** Run the task's commands. Anything touching money, compliance or the bid path needs a test. Never weaken or skip a test to get green.
- **Secrets.** `.env` stays local. New settings go in `.env.example` with an empty value.
- **Network.** No new published ports, wider DB users or looser CORS unless the task asks for it.

## Git

- One task, one branch (`task/NNN-short-name`), one pull request into `main`.
- Before pushing: `git fetch origin && git rebase origin/main`, then rerun the tests. If the rebase conflicts in another lane's files, stop and report.
- Commit messages are plain sentences: what changed and why.
- No AI attribution in commits or PRs: no `Co-authored-by`, `Made-with` or `Generated with` lines. Sam is the sole author. Turn on the hook once per clone: `git config core.hooksPath .githooks`.
- Only the planner commits straight to `main`, and only in planner-owned folders. Never force-push `main`.

## Test commands

| Area | Command |
|---|---|
| campaign-api | `cd services/campaign-api && pytest` |
| brain (compiler) | `cd services/brain && PYTHONPATH=../../packages/ruleset/python pytest` |
| ingest | `cd services/ingest && pytest` (from task 003) |
| bidder | `cd services/bidder && go test ./...` |
| ssp-simulator | `cd services/ssp-simulator && go test ./...` |
| agents | `python -m pytest agents/tests` (from repo root) |
| ruleset | `cd packages/ruleset/python && pytest` |
| Ops Console | `cd apps/web && npm run build` |
| Advertiser App | `cd apps/advertiser && npm run build && npm run test:e2e` (from task 004) |
| whole stack | `docker compose -f infra/docker-compose.yml up -d --build` |
