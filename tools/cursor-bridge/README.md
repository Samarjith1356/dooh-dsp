# cursor-bridge

Lets Claude (in the Claude desktop app, chat or Cowork) start and watch Cursor CLI agents on this PC.

Every Cursor agent works in its own git worktree in `..\dooh-dsp-worktrees\`, so your own working copy is never touched. Each job keeps a log in `.cursor-bridge\jobs\<job id>\output.log`.

## Install (once)

1. Double-click `setup.cmd`. It:
   - installs the Cursor CLI if needed,
   - turns on the repo's commit hook,
   - removes the old connector entry from earlier attempts,
   - logs the Cursor CLI in (approve it in the browser),
   - opens Claude's installer for `cursor-bridge.mcpb`.
2. In Claude, click **Install** and check that the repo folder is your `dooh-dsp` clone.
3. Tell Claude: "extension installed".

If the installer doesn't open, go to Claude **Settings > Extensions > Advanced settings > Install Extension** and pick `tools\cursor-bridge\cursor-bridge.mcpb`.

## What Claude can do with it

| Tool | What it does |
|---|---|
| `cursor_check` | Health check: repo, Cursor CLI, login, running jobs. `probe` runs a one-line test prompt. |
| `cursor_login` | Starts the Cursor CLI login and returns the link. |
| `cursor_start_task` | Starts a Cursor agent on `tasks/NNN-*.md`, following `.cursor/commands/do-task.md`. |
| `cursor_start` | Starts a Cursor agent with a free-form prompt. |
| `cursor_status` | Lists jobs, or shows one job with its recent log. |
| `cursor_output` | Reads more of a job's log. |
| `cursor_stop` | Stops a running job. |
| `cursor_remove_worktree` | Removes a finished job's worktree. Refuses if there is unpushed work. |

At most 3 agents run at once (change it in the extension's settings). A job is stopped after 90 minutes.

## Notes

- Agents run with `--trust --force`: they can edit files and run commands inside their worktree without asking. Branch protection and review on GitHub are the safety net.
- If Claude restarts while a job runs, the Cursor agent keeps going. The job shows `unsupervised` until it ends.
- To rebuild the extension: `npx -y @anthropic-ai/mcpb pack <folder with manifest.json and server/>`.
