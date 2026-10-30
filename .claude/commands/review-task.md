---
description: Review a Cursor task branch and record the verdict in the task file
argument-hint: <task number, e.g. 003>
---
Review task $ARGUMENTS.

1. Run `git fetch origin`. Find the branch `task/$ARGUMENTS-*` on origin, check it out and pull. If there is no such branch, stop and tell Sam.
2. Check that `tasks/$ARGUMENTS-*.md` has status `in-review`. If it has another status, stop and say what it is.
3. Give the review to the `reviewer` subagent with the task number. If the task's `extra_review` lists `security` or `qa`, give it to those subagents as well. They can run in parallel. Don't review it yourself, and don't edit code.
4. Copy each verdict word for word into the task file's Review section, under `### Round N (YYYY-MM-DD)`, with one sub-heading per reviewer.
5. Set the status. If every reviewer approved, `approved`. If any reviewer said NEEDS SAM, `needs-sam`. Otherwise `changes-requested`.
6. Commit only the task file, with the message `Review task $ARGUMENTS: <status>`, and push the branch.
7. Tell Sam in one line, then:
   - approved: the PR link, or the compare link if there is no PR
   - changes requested: "Run /do-task $ARGUMENTS in Cursor."
   - needs Sam: the question, in one sentence
