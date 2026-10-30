# Do task

Build the task whose number Sam typed after the command, for example `/do-task 003`.

1. Run `git fetch origin`. If a branch `task/<number>-*` exists on origin, check it out and pull. If not, check out `origin/main` and create `task/<number>-<short-name>`, using the branch name in the task file.
2. Open `tasks/<number>-*.md` and check three things before going further:
   - The status is `ready` or `changes-requested`. Otherwise stop and tell Sam what it is.
   - `sam_signoff` is `not-needed` or `approved`. If it says `needed`, stop: Sam hasn't approved the business rules yet (D-014).
   - Every task in `depends_on` shows status `merged` in `handbook/STATUS.md`. Otherwise stop and say which one is missing.
   - Note the `lane` and the "Files you may touch" list. You edit nothing outside them.
3. If this is your first task in this repo, read `handbook/README.md` and the files it lists. Every time, read the rows in `docs/build-log.csv` for your area. Always read `AGENTS.md`, every contract and file under Context, and the code the task points to before you edit.
4. Set status `building`, commit and push.
5. Build exactly what is under Scope and nothing under Out of scope. If something is unclear, or needs a product, architecture or contract decision the task doesn't make, write the question under Open questions, set status `blocked`, commit, push and stop.
6. If the status was `changes-requested`, work through every numbered item in the latest Review round and answer each one in the Builder report.
7. Run every command under Tests and fix the failures. Never skip or weaken a test.
8. Fill in the Builder report:
   - the files changed, and what each change does
   - each acceptance criterion, with its evidence (test name, command output, query result)
   - "Found along the way": anything you noticed but did not touch
   - "Handbook or contract updates needed": anything the planner should change
   - "Log entries": your mistakes, what worked well, ideas and risks, one line each with type, area and lesson (see `docs/build-log.md`)
9. Set status `in-review`. Run `git fetch origin && git rebase origin/main` and rerun the tests. If the rebase conflicts in files outside your lane, stop and report. Commit with a plain message and no attribution lines, then push.
10. If the `gh` CLI is available, open a pull request into `main` titled `Task <number>: <title>` that links the task file. If not, tell Sam the branch is pushed.
11. Reply to Sam in three lines: the branch, the test result, and anything he has to decide.
