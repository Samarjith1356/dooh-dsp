# Handbook: start here

This folder is the shared memory for everyone building dooh-dsp: Sam, Claude, the Cursor agents and Claude Code. Any agent new to the repo reads it in this order before touching code. It takes about ten minutes.

| Read | What you learn |
|---|---|
| [01-mission-and-product.md](01-mission-and-product.md) | What we're building, for whom, and what the prototype must prove |
| [02-dooh-101.md](02-dooh-101.md) | How programmatic outdoor advertising works, and the words we use |
| [03-architecture.md](03-architecture.md) | What runs where today, the target design, and the rules that keep the bid path fast |
| [04-irish-ad-rules.md](04-irish-ad-rules.md) | What may be shown where, and how the product enforces it |
| [05-roadmap.md](05-roadmap.md) | Sprints, gates, and what "ready to go live" means |
| [06-build-team.md](06-build-team.md) | Which agent does what, who owns which folders, and how work moves |
| [STATUS.md](STATUS.md) | What's being built now, what's blocked, what's waiting on Sam |

Then read these:

- [`AGENTS.md`](../AGENTS.md): the rules every coding tool follows
- [`docs/DECISIONS.md`](../docs/DECISIONS.md): decisions made and still open
- [`docs/build-log.csv`](../docs/build-log.csv): every decision, mistake, win, idea and risk so far, one row each. Read the rows for your area before you start ([how](../docs/build-log.md))
- [`tasks/BACKLOG.md`](../tasks/BACKLOG.md): the priority queue (D-013)
- [`contracts/`](../contracts/): the interfaces between lanes, which no builder changes alone
- [`tasks/`](../tasks/): the work orders

## Keeping it true

Claude (the planner) updates `STATUS.md` after every merge, and updates the handbook whenever a decision changes it. If the handbook and the code disagree, the code wins. Say so in your Builder report so the handbook gets fixed.

## Public repo note

This repo is public for now. Commercial details (pricing, partners, finances) live in the company plan, not in this folder.
