#!/usr/bin/env node
// cursor-bridge: lets Claude start Cursor agents on this PC.
//
// A small MCP server over stdio with no dependencies (runs on the Node built into
// the Claude desktop app). It works only inside the repo named by DOOH_REPO, starts
// every Cursor agent in its own git worktree so your own working copy is never
// touched, and keeps a log for every job.
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const cp = require('child_process');
const readline = require('readline');

const VERSION = '0.2.0';
const IS_WIN = process.platform === 'win32';
const env = (k, d) => (process.env[k] && process.env[k].trim()) || d;
const REPO = path.resolve(env('DOOH_REPO', path.join(os.homedir(), 'dooh-dsp')));
const WORKTREES = path.resolve(env('BRIDGE_WORKTREES', REPO + '-worktrees'));
const BRIDGE_DIR = path.join(REPO, '.cursor-bridge');
const JOBS = path.join(BRIDGE_DIR, 'jobs');
const MAX_JOBS = Math.max(1, parseInt(env('BRIDGE_MAX_JOBS', '3'), 10) || 3);
const TIMEOUT_MIN = Math.max(5, parseInt(env('BRIDGE_JOB_TIMEOUT_MIN', '90'), 10) || 90);
const AGENT_FLAGS = env('CURSOR_AGENT_FLAGS', '-p --trust --force --output-format text').split(/\s+/).filter(Boolean);
const PROMPT_FILE = '.bridge-prompt.md';
const TASK_RE = /^\d{3}$/;
const REF_RE = /^[A-Za-z0-9._/-]{1,100}$/;
const JOB_RE = /^[A-Za-z0-9._-]{1,80}$/;

// ---------- helpers ----------

const now = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z');
const log = (m) => process.stderr.write(`[cursor-bridge] ${m}\n`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function quoteWin(args) {
  return args.map((a) => (/[\s"]/.test(a) ? '"' + a.replace(/"/g, '\\"') + '"' : a)).join(' ');
}

function agentCommand(agent, args) {
  // On Windows the Cursor CLI is a PowerShell script (agent.ps1); .cmd shims go through cmd.exe.
  const low = agent.toLowerCase();
  if (IS_WIN && low.endsWith('.ps1')) {
    return { cmd: 'powershell.exe', args: ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', agent, ...args], verbatim: false };
  }
  if (IS_WIN && (low.endsWith('.cmd') || low.endsWith('.bat'))) {
    return { cmd: 'cmd.exe', args: ['/d', '/s', '/c', '"' + quoteWin([agent, ...args]) + '"'], verbatim: true };
  }
  return { cmd: agent, args, verbatim: false };
}

function run(cmd, args, { cwd, timeoutSec = 120, verbatim = false } = {}) {
  const r = cp.spawnSync(cmd, args, {
    cwd, encoding: 'utf8', timeout: timeoutSec * 1000, windowsHide: true,
    windowsVerbatimArguments: verbatim, input: '',
  });
  const out = (r.stdout || '') + (r.stderr || '');
  if (r.error && r.error.code === 'ETIMEDOUT') return { code: 124, out: out + `\n(timed out after ${timeoutSec}s)` };
  if (r.error) return { code: 127, out: String(r.error.message || r.error) };
  return { code: r.status === null ? 1 : r.status, out };
}

const git = (args, opts = {}) => run('git', args, { cwd: REPO, ...opts });

function runAgent(agent, args, opts = {}) {
  const c = agentCommand(agent, args);
  return run(c.cmd, c.args, { ...opts, verbatim: c.verbatim });
}

function findOnPath(names) {
  const exts = IS_WIN ? ['', '.cmd', '.exe', '.ps1'] : [''];
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    for (const n of names) for (const e of exts) {
      const p = path.join(dir, n + e);
      try { if (dir && fs.statSync(p).isFile()) return p; } catch (_) { /* keep looking */ }
    }
  }
  return null;
}

function findAgent() {
  const explicit = env('CURSOR_AGENT_PATH', '');
  if (explicit && fs.existsSync(explicit)) return explicit;
  const candidates = [];
  if (IS_WIN) {
    const base = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'cursor-agent');
    for (const f of ['agent.cmd', 'agent.exe', 'agent.ps1', 'cursor-agent.cmd', 'cursor-agent.exe', 'cursor-agent.ps1']) candidates.push(path.join(base, f));
  }
  for (const f of ['agent', 'cursor-agent']) candidates.push(path.join(os.homedir(), '.local', 'bin', f));
  for (const c of candidates) if (fs.existsSync(c)) return c;
  return findOnPath(['agent', 'cursor-agent']);
}

function pidAlive(pid) {
  if (!pid) return false;
  try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; }
}

function killTree(pid) {
  if (!pid) return;
  if (IS_WIN) { run('taskkill', ['/PID', String(pid), '/T', '/F'], { timeoutSec: 30 }); return; }
  try { process.kill(-pid, 'SIGKILL'); } catch (_) { try { process.kill(pid, 'SIGKILL'); } catch (__) { /* gone */ } }
}

function jobDir(id) {
  if (!JOB_RE.test(id || '')) throw new Error('bad job id');
  return path.join(JOBS, id);
}
const loadMeta = (jd) => JSON.parse(fs.readFileSync(path.join(jd, 'meta.json'), 'utf8'));
function saveMeta(jd, meta) {
  const tmp = path.join(jd, 'meta.json.tmp');
  fs.writeFileSync(tmp, JSON.stringify(meta, null, 2));
  fs.renameSync(tmp, path.join(jd, 'meta.json'));
}

function tail(file, lines) {
  try {
    const buf = fs.readFileSync(file);
    const text = buf.subarray(Math.max(0, buf.length - 200000)).toString('utf8');
    return text.split(/\r?\n/).slice(-lines).join('\n');
  } catch (_) { return ''; }
}

const ACTIVE = new Set(['starting', 'running', 'stopping']);
function refresh(meta, jd) {
  if (!ACTIVE.has(meta.status) || Date.now() / 1000 - (meta.created_ts || 0) < 30) return meta;
  if (pidAlive(meta.runner_pid)) return meta;
  if (pidAlive(meta.agent_pid)) {
    // The supervisor went away (e.g. Claude restarted) but Cursor is still working.
    if (!meta.unsupervised) { meta.unsupervised = true; saveMeta(jd, meta); }
    return meta;
  }
  meta.status = meta.unsupervised ? 'ended_unknown' : 'lost';
  meta.ended_at = now();
  saveMeta(jd, meta);
  return meta;
}

// A plain Node binary for the detached job runner. Inside Electron (Claude's built-in Node)
// we only use a real node from PATH; otherwise jobs are supervised by this server process.
function standaloneNode() {
  if (env('BRIDGE_IN_SERVER', '') === '1') return null;
  if (!process.versions.electron) return process.execPath;
  return findOnPath(['node']);
}

function allJobs() {
  if (!fs.existsSync(JOBS)) return [];
  const out = [];
  for (const name of fs.readdirSync(JOBS)) {
    const jd = path.join(JOBS, name);
    try { out.push(refresh(loadMeta(jd), jd)); } catch (_) { /* skip broken */ }
  }
  return out.sort((a, b) => (b.created_ts || 0) - (a.created_ts || 0));
}
const runningCount = () => allJobs().filter((m) => ACTIVE.has(m.status)).length;

function ensureLocalExcludes() {
  const p = path.join(REPO, '.git', 'info', 'exclude');
  try {
    const existing = fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '';
    const missing = ['.cursor-bridge/', PROMPT_FILE].filter((x) => !existing.includes(x));
    if (missing.length) {
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.appendFileSync(p, '\n' + missing.join('\n') + '\n');
    }
  } catch (e) { log(`could not update .git/info/exclude: ${e.message}`); }
}

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

// ---------- tools ----------

async function toolCheck({ probe = false } = {}) {
  const agent = findAgent();
  const info = {
    bridge_version: VERSION, node: process.version, repo: REPO,
    repo_exists: fs.existsSync(path.join(REPO, '.git')),
    worktrees_dir: WORKTREES, max_parallel_jobs: MAX_JOBS, job_timeout_minutes: TIMEOUT_MIN,
    agent_flags: AGENT_FLAGS,
    cursor_cli: agent || "NOT FOUND - install with: irm 'https://cursor.com/install?win32=true' | iex",
    git: git(['--version']).out.trim(),
    running_jobs: runningCount(),
  };
  if (agent) {
    info.cursor_cli_version = runAgent(agent, ['--version'], { timeoutSec: 60 }).out.trim().slice(-300);
    info.cursor_cli_status = runAgent(agent, ['status'], { timeoutSec: 60 }).out.trim().slice(-600);
    if (probe) {
      const r = runAgent(agent, ['-p', '--trust', 'Reply with exactly one word: ready'], { cwd: REPO, timeoutSec: 180 });
      info.probe_exit_code = r.code;
      info.probe_output = r.out.trim().slice(-600);
    }
  }
  return info;
}

async function toolLogin() {
  const agent = findAgent();
  if (!agent) throw new Error('Cursor CLI not found.');
  fs.mkdirSync(BRIDGE_DIR, { recursive: true });
  const logFile = path.join(BRIDGE_DIR, 'login.log');
  const fd = fs.openSync(logFile, 'w');
  const c = agentCommand(agent, ['login']);
  const child = cp.spawn(c.cmd, c.args, {
    detached: true, stdio: ['ignore', fd, fd], windowsHide: true, windowsVerbatimArguments: c.verbatim,
  });
  child.unref();
  fs.closeSync(fd);
  await sleep(8000);
  return {
    note: 'Cursor login started. A browser tab should open on this PC; if not, open the link below. ' +
      'Approve it with your Cursor account, then run cursor_check to confirm.',
    output: tail(logFile, 30),
  };
}

function startJob(kind, label, promptText, base, model) {
  if (!REF_RE.test(base || '')) throw new Error('bad base ref');
  if (runningCount() >= MAX_JOBS) throw new Error(`${MAX_JOBS} jobs already running. Wait for one to finish or stop one.`);
  const agent = findAgent();
  if (!agent) throw new Error('Cursor CLI not found. Run tools/cursor-bridge/setup.cmd first.');
  ensureLocalExcludes();
  let r = git(['fetch', '--quiet', 'origin'], { timeoutSec: 90 });
  if (r.code !== 0) throw new Error('git fetch failed: ' + r.out.trim().slice(-400));
  const id = `${label}-${stamp()}`;
  const jd = jobDir(id);
  fs.mkdirSync(jd, { recursive: true });
  fs.mkdirSync(WORKTREES, { recursive: true });
  const wt = path.join(WORKTREES, id);
  r = git(['worktree', 'add', '--detach', wt, base], { timeoutSec: 120 });
  if (r.code !== 0) throw new Error('git worktree add failed: ' + r.out.trim().slice(-400));
  fs.writeFileSync(path.join(wt, PROMPT_FILE), promptText);
  const meta = { id, kind, label, base, model: model || '', worktree: wt, status: 'starting', created_at: now(), created_ts: Date.now() / 1000 };
  saveMeta(jd, meta);
  const node = standaloneNode();
  if (node) {
    const runner = cp.spawn(node, [__filename, '--run-job', jd], { detached: true, stdio: 'ignore', windowsHide: true });
    runner.unref();
    // The runner writes its own pid and status into meta.json; writing here too could overwrite them.
  } else {
    superviseJob(jd);
  }
  return { job_id: id, worktree: wt, base, status: 'starting', next: 'Check progress with cursor_status.' };
}

async function toolStartTask({ task, base = 'origin/main', model = '', extra_instructions = '' }) {
  if (!TASK_RE.test(task || '')) throw new Error('task must be three digits, e.g. 003');
  let prompt =
    'You are a lane builder in the dooh-dsp repo, working headless for Claude (the planner).\n\n' +
    `Do task ${task}: follow the steps in .cursor/commands/do-task.md exactly, for task number ${task}.\n` +
    'Read AGENTS.md and handbook/README.md first if you have not worked in this repo before.\n' +
    `You are in a dedicated git worktree. Never edit, add or commit the file ${PROMPT_FILE}.\n` +
    'Commits must have no Co-authored-by, Made-with or Generated-with lines.\n' +
    "If you are blocked, follow the task's blocked procedure and stop.\n\n" +
    'Finish with exactly three lines: Branch: <name> / Tests: <result> / Needs Sam: <none or the question>.\n';
  if (extra_instructions) prompt += `\nAdditional instructions from the planner:\n${extra_instructions}\n`;
  return startJob('task', `task-${task}`, prompt, base, model);
}

async function toolStart({ prompt, base = 'origin/main', model = '', name = 'adhoc' }) {
  if (!prompt || prompt.length > 20000) throw new Error('prompt is required and must be under 20,000 characters');
  if (!JOB_RE.test(name)) throw new Error('name may only contain letters, digits, dot, dash and underscore');
  const text =
    'You are working headless in a dedicated git worktree of the dooh-dsp repo for Claude (the planner).\n' +
    `Follow AGENTS.md. Never edit, add or commit the file ${PROMPT_FILE}. Commits must have no ` +
    'Co-authored-by, Made-with or Generated-with lines.\n\n' + prompt + '\n';
  return startJob('adhoc', name, text, base, model);
}

async function toolStatus({ job_id = '' } = {}) {
  if (job_id) {
    const jd = jobDir(job_id);
    const meta = refresh(loadMeta(jd), jd);
    meta.log_tail = tail(path.join(jd, 'output.log'), 40);
    return meta;
  }
  return allJobs().slice(0, 20).map((m) => ({
    id: m.id, status: m.status, exit_code: m.exit_code, created_at: m.created_at, ended_at: m.ended_at, worktree: m.worktree,
  }));
}

async function toolOutput({ job_id, lines = 200 }) {
  const jd = jobDir(job_id);
  return tail(path.join(jd, 'output.log'), Math.max(1, Math.min(parseInt(lines, 10) || 200, 2000))) || '(no output yet)';
}

async function toolStop({ job_id }) {
  const jd = jobDir(job_id);
  const meta = loadMeta(jd);
  if (!['starting', 'running'].includes(meta.status)) return { job_id, status: meta.status, note: 'not running' };
  meta.status = 'stopping';
  saveMeta(jd, meta);
  killTree(meta.agent_pid);
  if (!meta.in_server && meta.runner_pid !== process.pid) killTree(meta.runner_pid);
  meta.status = 'stopped';
  meta.ended_at = now();
  saveMeta(jd, meta);
  return { job_id, status: 'stopped' };
}

async function toolRemoveWorktree({ job_id, force = false }) {
  const jd = jobDir(job_id);
  const meta = refresh(loadMeta(jd), jd);
  if (ACTIVE.has(meta.status)) throw new Error('job is still running; stop it first');
  const wt = meta.worktree;
  if (fs.existsSync(wt) && !force) {
    const dirty = git(['status', '--porcelain', '--untracked-files=no'], { cwd: wt }).out.trim();
    const unpushed = git(['log', '--oneline', 'HEAD', '--not', '--remotes'], { cwd: wt }).out.trim();
    if (dirty || unpushed) {
      return { removed: false, reason: 'worktree has uncommitted or unpushed work', uncommitted: dirty.slice(-800), unpushed: unpushed.slice(-800), note: 'pass force=true to remove anyway' };
    }
  }
  const r = git(['worktree', 'remove', '--force', wt]);
  meta.worktree_removed = r.code === 0;
  saveMeta(jd, meta);
  return { removed: r.code === 0, detail: r.out.trim().slice(-400) };
}

const TOOLS = {
  cursor_check: {
    fn: toolCheck,
    description: 'Health check: repo, Cursor CLI path, version and login status, git, running jobs. probe=true also runs a one-line test prompt through Cursor (uses a little Cursor usage).',
    schema: { type: 'object', properties: { probe: { type: 'boolean' } } },
  },
  cursor_login: {
    fn: toolLogin,
    description: 'Start the Cursor CLI login on this PC. Opens a browser for the user to approve and returns the login link from the CLI output.',
    schema: { type: 'object', properties: {} },
  },
  cursor_start_task: {
    fn: toolStartTask,
    description: 'Start a Cursor agent on a task file (tasks/NNN-*.md) in its own git worktree. It follows .cursor/commands/do-task.md and runs in the background. Returns a job_id.',
    schema: {
      type: 'object', required: ['task'], properties: {
        task: { type: 'string', description: 'Three-digit task number, e.g. 003' },
        base: { type: 'string', description: 'Git ref to start from. Default origin/main' },
        model: { type: 'string', description: 'Optional Cursor model name' },
        extra_instructions: { type: 'string' },
      },
    },
  },
  cursor_start: {
    fn: toolStart,
    description: 'Start a Cursor agent with a free-form prompt in a fresh git worktree (research, a fix, a question about the code). Runs in the background. Returns a job_id.',
    schema: {
      type: 'object', required: ['prompt'], properties: {
        prompt: { type: 'string' },
        base: { type: 'string', description: 'Git ref to start from. Default origin/main' },
        model: { type: 'string' },
        name: { type: 'string', description: 'Short label for the job id' },
      },
    },
  },
  cursor_status: {
    fn: toolStatus,
    description: "List recent jobs, or give one job's details and the last 40 log lines.",
    schema: { type: 'object', properties: { job_id: { type: 'string' } } },
  },
  cursor_output: {
    fn: toolOutput,
    description: "Read the last N lines of a job's Cursor output.",
    schema: { type: 'object', required: ['job_id'], properties: { job_id: { type: 'string' }, lines: { type: 'integer' } } },
  },
  cursor_stop: {
    fn: toolStop,
    description: 'Stop a running job and its Cursor agent.',
    schema: { type: 'object', required: ['job_id'], properties: { job_id: { type: 'string' } } },
  },
  cursor_remove_worktree: {
    fn: toolRemoveWorktree,
    description: "Delete a finished job's worktree. Refuses if it has uncommitted or unpushed work unless force=true.",
    schema: { type: 'object', required: ['job_id'], properties: { job_id: { type: 'string' }, force: { type: 'boolean' } } },
  },
};

// ---------- job supervisor ----------
// Runs either in a detached runner process (--run-job) or inside the server itself.
// The Cursor agent is always started detached with its output going to a file, so it
// keeps working even if the supervisor goes away.

function superviseJob(jd) {
  const meta = loadMeta(jd);
  meta.status = 'running';
  meta.runner_pid = process.pid;
  meta.in_server = process.argv[2] !== '--run-job';
  meta.started_at = now();
  saveMeta(jd, meta);
  const agent = findAgent();
  const logFile = path.join(jd, 'output.log');
  const fd = fs.openSync(logFile, 'a');
  const finish = (status, code) => {
    try { fs.appendFileSync(logFile, `\n[bridge] ${now()} agent exited with ${code} (${status})\n`); } catch (_) { /* ignore */ }
    const latest = loadMeta(jd);
    if (latest.status === 'stopping' || latest.status === 'stopped') status = 'stopped';
    Object.assign(latest, { status, exit_code: code, ended_at: now() });
    saveMeta(jd, latest);
  };
  if (!agent) { fs.writeSync(fd, '[bridge] Cursor CLI not found\n'); fs.closeSync(fd); finish('failed', null); return; }
  fs.writeSync(fd, `[bridge] ${now()} starting Cursor agent in ${meta.worktree}\n`);
  const args = [...AGENT_FLAGS];
  if (meta.model) args.push('--model', meta.model);
  args.push('--workspace', meta.worktree, `Read the file ${PROMPT_FILE} in the workspace root and do exactly what it says.`);
  const c = agentCommand(agent, args);
  let child;
  try {
    child = cp.spawn(c.cmd, c.args, {
      cwd: meta.worktree, stdio: ['ignore', fd, fd], windowsHide: true,
      windowsVerbatimArguments: c.verbatim, detached: true,
    });
  } catch (e) {
    fs.writeSync(fd, `[bridge] could not start Cursor CLI: ${e.message}\n`);
    fs.closeSync(fd);
    finish('failed', null);
    return;
  }
  fs.closeSync(fd); // the child holds its own handle
  meta.agent_pid = child.pid;
  saveMeta(jd, meta);
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; killTree(child.pid); }, TIMEOUT_MIN * 60 * 1000);
  child.on('error', (e) => { clearTimeout(timer); fs.appendFileSync(logFile, `[bridge] error: ${e.message}\n`); finish('failed', null); });
  child.on('exit', (code) => {
    clearTimeout(timer);
    finish(timedOut ? 'timed_out' : code === 0 ? 'finished' : 'failed', timedOut ? null : code);
  });
}

// ---------- MCP over stdio ----------

const send = (msg) => process.stdout.write(JSON.stringify(msg) + '\n');

async function handle(msg) {
  const { method, id } = msg;
  if (id === undefined || id === null) return; // notifications need no reply
  if (method === 'initialize') {
    const version = (msg.params && msg.params.protocolVersion) || '2025-06-18';
    return send({ jsonrpc: '2.0', id, result: { protocolVersion: version, capabilities: { tools: {} }, serverInfo: { name: 'cursor-bridge', version: VERSION } } });
  }
  if (method === 'ping') return send({ jsonrpc: '2.0', id, result: {} });
  if (method === 'tools/list') {
    return send({ jsonrpc: '2.0', id, result: { tools: Object.entries(TOOLS).map(([name, t]) => ({ name, description: t.description, inputSchema: t.schema })) } });
  }
  if (method === 'tools/call') {
    const params = msg.params || {};
    const tool = TOOLS[params.name];
    if (!tool) return send({ jsonrpc: '2.0', id, error: { code: -32602, message: `unknown tool ${params.name}` } });
    try {
      const result = await tool.fn(params.arguments || {});
      const text = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
      return send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text }] } });
    } catch (e) {
      return send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: `${e.name || 'Error'}: ${e.message}` }], isError: true } });
    }
  }
  return send({ jsonrpc: '2.0', id, error: { code: -32601, message: `unknown method ${method}` } });
}

function serve() {
  log(`v${VERSION} serving repo ${REPO}`);
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on('line', (line) => {
    line = line.trim();
    if (!line) return;
    let msg;
    try { msg = JSON.parse(line); } catch (_) { return send({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'parse error' } }); }
    for (const m of Array.isArray(msg) ? msg : [msg]) handle(m).catch((e) => log(`handler error: ${e.message}`));
  });
}

const argv = process.argv.slice(2);
if (argv[0] === '--run-job' && argv[1]) superviseJob(argv[1]);
else if (argv.includes('--self-test')) toolCheck({ probe: argv.includes('--probe') }).then((i) => console.log(JSON.stringify(i, null, 2)));
else serve();
