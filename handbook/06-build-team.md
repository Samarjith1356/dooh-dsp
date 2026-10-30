# The build team

## The decision: a small team in lanes, not one agent and not a swarm

- **One agent** is too slow for 14 weeks of scope. It also loses track of a codebase this size.
- **Many agents at once** (6-8) collide on shared files, copy the same wrong assumption in parallel, and pile up reviews faster than they can be checked. They also burn usage quickly.
- **Three builders in parallel**, each owning separate folders and working from written contracts, roughly triples throughput without the collisions. One planner keeps them pointed the same way, and one reviewer keeps them honest.

A fourth builder lane (Agents) switches on in Sprint 3, when the platform it builds on exists.

## Roster

| Agent | Tool | Job | Active from |
|---|---|---|---|
| Planner | Claude (claude.ai chat) | Specs, contracts, task briefs, decisions, this handbook, `STATUS.md` | Now |
| Trading builder | Cursor agent | Bid path: bidder, simulator, compiler, ingest, ruleset, ClickHouse | Sprint 0 |
| Platform builder | Cursor agent | Backend: campaign-api, accounts, wallet, compliance API, CI, infra | Sprint 0 |
| Experience builder | Cursor agent | Advertiser App and Ops Console | Sprint 0 |
| Agents builder | Cursor agent | Central Brain, enterprise agents, Advertiser Agent | Sprint 3 |
| Reviewer | Claude Code, `reviewer` subagent | Checks every branch before merge | Now |
| Security reviewer | Claude Code, `security` subagent | Auth, payments, secrets, network exposure | Sprint 1 |
| QA | Claude Code, `qa` subagent | End-to-end tests and UAT scripts | Sprint 2 |
| Sam | - | Priorities, business decisions, merges | Always |

## Lanes and folder ownership

A builder edits only its own lane's folders. A task may grant a listed extra file explicitly. Everything else is read-only to that builder.

| Lane | Owns |
|---|---|
| Trading | `services/bidder`, `services/ssp-simulator`, `services/brain` (later `services/compiler`), `services/ingest`, `packages/`, `infra/clickhouse/` |
| Platform | `services/campaign-api`, `infra/docker-compose.yml`, `.github/`, `.env.example` |
| Experience | `apps/web`, `apps/advertiser` |
| Agents | `agents/` |
| Planner only | `contracts/`, `handbook/`, `docs/DECISIONS.md`, `tasks/` (except the Builder report and status line) |

When a change crosses lanes, the planner splits it into one task per lane and writes the contract between them first.

## One lane, one agent, one task at a time

- Each lane has at most one Cursor agent running, on one task.
- Each agent works in its own git worktree (Cursor Agents Window -> new agent -> Worktree), so agents never share a working copy.
- Before pushing, the agent rebases on the latest `main` and reruns its tests. If the rebase conflicts in another lane's files, it stops and reports.

## How a task flows

```
Planner writes tasks/NNN (ready)
  -> Sam starts it in Cursor: /do-task NNN
  -> builder works on task/NNN-... (building) -> pushes (in-review)
  -> Sam runs /review-task NNN in Claude Code
       -> APPROVED: Sam merges, planner updates STATUS
       -> CHANGES REQUESTED: back to the builder, same command
       -> NEEDS SAM: a business question, answered in Claude chat
```

## Definition of done

- Every acceptance criterion is met, with evidence in the Builder report
- The task's tests and CI are green
- No edits outside the lane except files the task granted
- No new secrets, ports, or fake numbers presented as real
- The reviewer has approved, and a security review is done if the task asks for one

## When agents should stop and ask

Stop and ask when you need a product decision, a contract change, a new paid service or account, anything touching real money or real screens, or a choice that would be hard to undo. Write the question in the task's Open questions, set status `blocked`, and stop. The planner collects these and takes them to Sam in one batch.

## Getting the most from Cursor

- Use the **Agents Window** to run the three lane agents side by side, each in its own worktree.
- For a hard, self-contained problem (bidder latency, a tricky parser), `/best-of-n` lets several models try it, and the reviewer picks the best result.
- Default to Cursor's strongest model for Trading and Platform work. A faster model is fine for UI scaffolding.
- Parallel agents multiply usage, so keep an eye on the monthly limit in Cursor settings.
- Cloud agents (triggered from GitHub or your phone) come later. They commit under Cursor's name, so we will switch to them only with a merge setup that keeps Sam as the author.
