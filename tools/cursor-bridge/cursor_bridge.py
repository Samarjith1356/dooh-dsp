#!/usr/bin/env python3
"""cursor-bridge: lets Claude start Cursor agents on this PC.

A small MCP server over stdio, standard library only. It works only inside the
repo named by DOOH_REPO, starts every Cursor agent in its own git worktree so
your own working copy is never touched, and keeps a log for every job.

Run modes:
  python cursor_bridge.py               MCP server (Claude desktop starts this)
  python cursor_bridge.py --self-test   print a health check and exit
  python cursor_bridge.py --run-job DIR internal: runs one agent job
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

VERSION = "0.1.0"
IS_WIN = os.name == "nt"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.environ.get("DOOH_REPO") or os.path.join(HERE, "..", ".."))
WORKTREES = os.path.abspath(os.environ.get("BRIDGE_WORKTREES") or REPO + "-worktrees")
JOBS = os.path.join(REPO, ".cursor-bridge", "jobs")
MAX_JOBS = int(os.environ.get("BRIDGE_MAX_JOBS", "3"))
TIMEOUT_MIN = int(os.environ.get("BRIDGE_JOB_TIMEOUT_MIN", "90"))
AGENT_FLAGS = os.environ.get("CURSOR_AGENT_FLAGS", "-p --trust --force --output-format text").split()
PROMPT_FILE = ".bridge-prompt.md"
NO_WINDOW = 0x08000000 if IS_WIN else 0
DETACHED = (0x00000008 | 0x00000200) if IS_WIN else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

TASK_RE = re.compile(r"^\d{3}$")
REF_RE = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
JOB_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


# ---------- helpers ----------

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def log(msg):
    sys.stderr.write(f"[cursor-bridge] {msg}\n")
    sys.stderr.flush()


def run(cmd, cwd=None, timeout=120):
    """Run a short command and return (exit_code, combined output)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError as e:
        return 127, str(e)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"


def git(*args, cwd=REPO, timeout=120):
    return run(["git", *args], cwd=cwd, timeout=timeout)


def find_agent():
    explicit = os.environ.get("CURSOR_AGENT_PATH")
    if explicit and os.path.exists(explicit):
        return explicit
    for name in ("agent", "cursor-agent"):
        found = shutil.which(name)
        if found:
            return found
    candidates = []
    if IS_WIN:
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "cursor-agent")
        candidates += [os.path.join(base, f) for f in ("agent.cmd", "agent.exe", "cursor-agent.cmd", "cursor-agent.exe")]
    home = os.path.expanduser("~")
    candidates += [os.path.join(home, ".local", "bin", n) for n in ("agent", "cursor-agent")]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def agent_command(agent, args):
    """Build the process command. Windows .cmd shims must go through cmd.exe."""
    if IS_WIN and agent.lower().endswith((".cmd", ".bat")):
        return 'cmd.exe /d /s /c "' + subprocess.list2cmdline([agent, *args]) + '"'
    return [agent, *args]


def pid_alive(pid):
    if not pid:
        return False
    if IS_WIN:
        code, out = run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], timeout=20)
        return str(int(pid)) in out
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def kill_tree(pid):
    if not pid:
        return
    if IS_WIN:
        run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], timeout=30)
    else:
        try:
            os.killpg(os.getpgid(int(pid)), 9)
        except OSError:
            pass


def job_dir(job_id):
    if not JOB_RE.match(job_id or ""):
        raise ValueError("bad job id")
    return os.path.join(JOBS, job_id)


def load_meta(jd):
    with open(os.path.join(jd, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def save_meta(jd, meta):
    tmp = os.path.join(jd, "meta.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    os.replace(tmp, os.path.join(jd, "meta.json"))


def tail(path, lines):
    try:
        with open(path, "rb") as f:
            data = f.read()[-200_000:]
        text = data.decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])
    except FileNotFoundError:
        return ""


def refresh(meta, jd):
    """Mark a job as lost if its runner died without recording an ending."""
    if meta.get("status") in ("starting", "running", "stopping") and not pid_alive(meta.get("runner_pid")):
        if time.time() - meta.get("created_ts", 0) > 30:
            meta["status"] = "lost"
            meta["ended_at"] = now()
            save_meta(jd, meta)
    return meta


def all_jobs():
    if not os.path.isdir(JOBS):
        return []
    out = []
    for name in os.listdir(JOBS):
        jd = os.path.join(JOBS, name)
        try:
            out.append(refresh(load_meta(jd), jd))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda m: m.get("created_ts", 0), reverse=True)


def running_count():
    return sum(1 for m in all_jobs() if m.get("status") in ("starting", "running", "stopping"))


def ensure_local_excludes():
    path = os.path.join(REPO, ".git", "info", "exclude")
    try:
        existing = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        missing = [p for p in (".cursor-bridge/", PROMPT_FILE) if p not in existing]
        if missing:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(missing) + "\n")
    except OSError as e:
        log(f"could not update .git/info/exclude: {e}")


# ---------- tools ----------

def tool_check(probe=False):
    agent = find_agent()
    info = {
        "bridge_version": VERSION,
        "repo": REPO,
        "repo_exists": os.path.isdir(os.path.join(REPO, ".git")),
        "worktrees_dir": WORKTREES,
        "max_parallel_jobs": MAX_JOBS,
        "job_timeout_minutes": TIMEOUT_MIN,
        "agent_flags": AGENT_FLAGS,
        "cursor_cli": agent or "NOT FOUND - install with: irm 'https://cursor.com/install?win32=true' | iex",
        "git": git("--version")[1].strip(),
        "running_jobs": running_count(),
    }
    if agent:
        info["cursor_cli_version"] = run(agent_command(agent, ["--version"]), timeout=60)[1].strip()[-300:]
        info["cursor_cli_status"] = run(agent_command(agent, ["status"]), timeout=60)[1].strip()[-600:]
        if probe:
            code, out = run(agent_command(agent, ["-p", "--trust", "Reply with exactly one word: ready"]),
                            cwd=REPO, timeout=180)
            info["probe_exit_code"] = code
            info["probe_output"] = out.strip()[-600:]
    return info


def _start_job(kind, label, prompt_text, base, model):
    if not REF_RE.match(base or ""):
        raise ValueError("bad base ref")
    if running_count() >= MAX_JOBS:
        raise RuntimeError(f"{MAX_JOBS} jobs already running. Wait for one to finish or stop one.")
    agent = find_agent()
    if not agent:
        raise RuntimeError("Cursor CLI not found. Run tools/cursor-bridge/setup.ps1 first.")
    ensure_local_excludes()
    code, out = git("fetch", "--quiet", "origin", timeout=180)
    if code != 0:
        raise RuntimeError(f"git fetch failed: {out.strip()[-400:]}")
    job_id = f"{label}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    jd = job_dir(job_id)
    os.makedirs(jd, exist_ok=True)
    wt = os.path.join(WORKTREES, job_id)
    os.makedirs(WORKTREES, exist_ok=True)
    code, out = git("worktree", "add", "--detach", wt, base, timeout=180)
    if code != 0:
        raise RuntimeError(f"git worktree add failed: {out.strip()[-400:]}")
    with open(os.path.join(wt, PROMPT_FILE), "w", encoding="utf-8") as f:
        f.write(prompt_text)
    meta = {"id": job_id, "kind": kind, "label": label, "base": base, "model": model or "",
            "worktree": wt, "status": "starting", "created_at": now(), "created_ts": time.time()}
    save_meta(jd, meta)
    runner = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--run-job", jd],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              creationflags=DETACHED, start_new_session=not IS_WIN, close_fds=True)
    meta["runner_pid"] = runner.pid
    save_meta(jd, meta)
    return {"job_id": job_id, "worktree": wt, "base": base, "status": "starting",
            "next": "Check progress with cursor_status."}


def tool_start_task(task, base="origin/main", model="", extra_instructions=""):
    if not TASK_RE.match(task or ""):
        raise ValueError("task must be three digits, e.g. 003")
    prompt = (
        f"You are a lane builder in the dooh-dsp repo, working headless for Claude (the planner).\n\n"
        f"Do task {task}: follow the steps in .cursor/commands/do-task.md exactly, for task number {task}.\n"
        f"Read AGENTS.md and handbook/README.md first if you have not worked in this repo before.\n"
        f"You are in a dedicated git worktree. Never edit, add or commit the file {PROMPT_FILE}.\n"
        f"Commits must have no Co-authored-by, Made-with or Generated-with lines.\n"
        f"If you are blocked, follow the task's blocked procedure and stop.\n\n"
        f"Finish with exactly three lines: Branch: <name> / Tests: <result> / Needs Sam: <none or the question>.\n"
    )
    if extra_instructions:
        prompt += f"\nAdditional instructions from the planner:\n{extra_instructions}\n"
    return _start_job("task", f"task-{task}", prompt, base, model)


def tool_start(prompt, base="origin/main", model="", name="adhoc"):
    if not prompt or len(prompt) > 20000:
        raise ValueError("prompt is required and must be under 20,000 characters")
    if not JOB_RE.match(name or ""):
        raise ValueError("name may only contain letters, digits, dot, dash and underscore")
    text = (f"You are working headless in a dedicated git worktree of the dooh-dsp repo for Claude (the planner).\n"
            f"Follow AGENTS.md. Never edit, add or commit the file {PROMPT_FILE}. Commits must have no "
            f"Co-authored-by, Made-with or Generated-with lines.\n\n{prompt}\n")
    return _start_job("adhoc", name, text, base, model)


def tool_status(job_id=""):
    if job_id:
        jd = job_dir(job_id)
        meta = refresh(load_meta(jd), jd)
        meta["log_tail"] = tail(os.path.join(jd, "output.log"), 40)
        return meta
    jobs = all_jobs()[:20]
    return [{k: m.get(k) for k in ("id", "status", "exit_code", "created_at", "ended_at", "worktree")} for m in jobs]


def tool_output(job_id, lines=200):
    jd = job_dir(job_id)
    return tail(os.path.join(jd, "output.log"), max(1, min(int(lines), 2000))) or "(no output yet)"


def tool_stop(job_id):
    jd = job_dir(job_id)
    meta = load_meta(jd)
    if meta.get("status") not in ("starting", "running"):
        return {"job_id": job_id, "status": meta.get("status"), "note": "not running"}
    meta["status"] = "stopping"
    save_meta(jd, meta)
    kill_tree(meta.get("agent_pid"))
    kill_tree(meta.get("runner_pid"))
    meta["status"] = "stopped"
    meta["ended_at"] = now()
    save_meta(jd, meta)
    return {"job_id": job_id, "status": "stopped"}


def tool_remove_worktree(job_id, force=False):
    jd = job_dir(job_id)
    meta = refresh(load_meta(jd), jd)
    if meta.get("status") in ("starting", "running", "stopping"):
        raise RuntimeError("job is still running; stop it first")
    wt = meta["worktree"]
    if os.path.isdir(wt) and not force:
        _, dirty = git("status", "--porcelain", "--untracked-files=no", cwd=wt)
        _, unpushed = git("log", "--oneline", "HEAD", "--not", "--remotes", cwd=wt)
        if dirty.strip() or unpushed.strip():
            return {"removed": False, "reason": "worktree has uncommitted or unpushed work",
                    "uncommitted": dirty.strip()[-800:], "unpushed": unpushed.strip()[-800:],
                    "note": "pass force=true to remove anyway"}
    code, out = git("worktree", "remove", "--force", wt)
    meta["worktree_removed"] = code == 0
    save_meta(jd, meta)
    return {"removed": code == 0, "detail": out.strip()[-400:]}


TOOLS = {
    "cursor_check": {
        "fn": tool_check,
        "description": "Health check: repo, Cursor CLI path, version and login status, git, running jobs. "
                       "probe=true also runs a one-line test prompt through Cursor (uses a little Cursor usage).",
        "schema": {"type": "object", "properties": {"probe": {"type": "boolean"}}},
    },
    "cursor_start_task": {
        "fn": tool_start_task,
        "description": "Start a Cursor agent on a task file (tasks/NNN-*.md) in its own git worktree. It follows "
                       ".cursor/commands/do-task.md and runs in the background. Returns a job_id.",
        "schema": {"type": "object", "required": ["task"], "properties": {
            "task": {"type": "string", "description": "Three-digit task number, e.g. 003"},
            "base": {"type": "string", "description": "Git ref to start from. Default origin/main"},
            "model": {"type": "string", "description": "Optional Cursor model name"},
            "extra_instructions": {"type": "string"}}},
    },
    "cursor_start": {
        "fn": tool_start,
        "description": "Start a Cursor agent with a free-form prompt in a fresh git worktree (research, a fix, a "
                       "question about the code). Runs in the background. Returns a job_id.",
        "schema": {"type": "object", "required": ["prompt"], "properties": {
            "prompt": {"type": "string"},
            "base": {"type": "string", "description": "Git ref to start from. Default origin/main"},
            "model": {"type": "string"},
            "name": {"type": "string", "description": "Short label for the job id"}}},
    },
    "cursor_status": {
        "fn": tool_status,
        "description": "List recent jobs, or give one job's details and the last 40 log lines.",
        "schema": {"type": "object", "properties": {"job_id": {"type": "string"}}},
    },
    "cursor_output": {
        "fn": tool_output,
        "description": "Read the last N lines of a job's Cursor output.",
        "schema": {"type": "object", "required": ["job_id"], "properties": {
            "job_id": {"type": "string"}, "lines": {"type": "integer"}}},
    },
    "cursor_stop": {
        "fn": tool_stop,
        "description": "Stop a running job and its Cursor agent.",
        "schema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}},
    },
    "cursor_remove_worktree": {
        "fn": tool_remove_worktree,
        "description": "Delete a finished job's worktree. Refuses if it has uncommitted or unpushed work unless "
                       "force=true.",
        "schema": {"type": "object", "required": ["job_id"], "properties": {
            "job_id": {"type": "string"}, "force": {"type": "boolean"}}},
    },
}


# ---------- job runner ----------

def run_job(jd):
    meta = load_meta(jd)
    meta["status"] = "running"
    meta["runner_pid"] = os.getpid()
    meta["started_at"] = now()
    save_meta(jd, meta)
    agent = find_agent()
    args = list(AGENT_FLAGS)
    if meta.get("model"):
        args += ["--model", meta["model"]]
    args += ["--workspace", meta["worktree"],
             f"Read the file {PROMPT_FILE} in the workspace root and do exactly what it says."]
    with open(os.path.join(jd, "output.log"), "ab") as out:
        out.write(f"[bridge] {now()} starting Cursor agent in {meta['worktree']}\n".encode())
        out.flush()
        try:
            proc = subprocess.Popen(agent_command(agent, args), cwd=meta["worktree"], stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    creationflags=NO_WINDOW, start_new_session=not IS_WIN)
        except OSError as e:
            out.write(f"[bridge] could not start Cursor CLI: {e}\n".encode())
            meta.update(status="failed", exit_code=None, ended_at=now())
            save_meta(jd, meta)
            return
        meta["agent_pid"] = proc.pid
        save_meta(jd, meta)
        try:
            code = proc.wait(timeout=TIMEOUT_MIN * 60)
            status = "finished" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            kill_tree(proc.pid)
            code, status = None, "timed_out"
        out.write(f"\n[bridge] {now()} agent exited with {code} ({status})\n".encode())
    latest = load_meta(jd)
    if latest.get("status") in ("stopping", "stopped"):
        status = "stopped"
    latest.update(status=status, exit_code=code, ended_at=now())
    save_meta(jd, latest)


# ---------- MCP over stdio ----------

def send(msg):
    sys.stdout.buffer.write((json.dumps(msg) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return  # notifications need no reply
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "cursor-bridge", "version": VERSION}}})
    if method == "ping":
        return send({"jsonrpc": "2.0", "id": mid, "result": {}})
    if method == "tools/list":
        return send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [
            {"name": n, "description": t["description"], "inputSchema": t["schema"]} for n, t in TOOLS.items()]}})
    if method == "tools/call":
        params = msg.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            return send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}})
        try:
            result = tool["fn"](**args)
            text = result if isinstance(result, str) else json.dumps(result, indent=2)
            return send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}]}})
        except Exception as e:  # report tool errors to Claude instead of crashing
            return send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}})
    return send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})


def serve():
    log(f"v{VERSION} serving repo {REPO}")
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        for m in (msg if isinstance(msg, list) else [msg]):
            handle(m)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--run-job":
        run_job(sys.argv[2])
    elif "--self-test" in sys.argv:
        print(json.dumps(tool_check(probe="--probe" in sys.argv), indent=2))
    else:
        serve()
