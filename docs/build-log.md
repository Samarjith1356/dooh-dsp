# Build log

`docs/build-log.csv` is the company's memory of how the build went. One row per event: every decision, new workflow, mistake, thing that worked well, idea, risk and open question. It opens in Excel or Google Sheets, and GitHub shows it as a searchable table.

## Why it exists

So no agent, human or AI, makes the same mistake twice or re-argues a settled question. Before starting a task, read the rows for your area. Mistakes and lessons first.

```
python -c "import csv; [print(r['id'], r['type'], r['title'], '->', r['lesson_or_next_step']) for r in csv.DictReader(open('docs/build-log.csv')) if r['area'] in ('trading', 'money')]"
```

## Columns

| Column | What goes in it |
|---|---|
| `id` | `L-001`, `L-002`, ... in order. Never reuse or renumber |
| `date` | `YYYY-MM-DD` |
| `type` | `decision`, `workflow`, `mistake`, `win`, `idea`, `risk`, `question` |
| `area` | `trading`, `platform`, `experience`, `agents`, `money`, `compliance`, `security`, `git`, `tooling`, `build`, `product`, `company` |
| `title` | One line someone can scan |
| `what_happened` | The facts, in a sentence or two |
| `impact` | What it changed, cost or saved |
| `lesson_or_next_step` | What to do differently, or what happens next. Write this so the next agent can act on it |
| `status` | `adopted`, `fixed`, `open`, `planned`, `parked`, `rejected` |
| `owner` | Who decided or who acts: Sam, Claude, a lane |
| `refs` | D-number, task, file or PR |

## Rules

- **One writer.** Only the planner edits the CSV, straight on `main`. Builders write their rows under "Log entries" in the task's Builder report, and the planner copies them in after the merge. This keeps parallel branches from conflicting on one file.
- **Append only.** To change an old row, add a new one with a `refs` pointing to it. The exception is `status`, which the planner updates in place (for example `open` to `fixed`).
- **Decisions live in two places.** The full reasoning stays in `docs/DECISIONS.md`. The log row is the one-line summary with the D-number in `refs`.
- **Honest.** Mistakes are logged plainly, with no blame. The point is the lesson.
- **Plain text.** Plain ASCII, no line breaks inside a cell.
