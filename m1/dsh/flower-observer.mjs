// Local metadata observer for DeepSeek Harness 0.2.1-rc.5.
// No network, credentials, message bodies, prompts or approval decisions.
import { mkdirSync, writeFileSync, renameSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';

// The bridge treats a heartbeat older than 3s as "DSH is not running".
const TICK_MS = 500;
const HEARTBEAT_MS = 1000;
// One failed read is a blip; a persistent one means the runtime changed.
const FAILURE_LIMIT = 3;

export function foldEvent(state, event) {
  if (event?.type === 'turn/start' || event?.type === 'turn/end') {
    state.questions.clear(); state.approvals.clear();
    return;
  }
  const d = event?.data;
  if (!d) return;
  if (event.type === 'tool/call' && d.name === 'ask_user_question') {
    state.questions.add(d.callId);
  } else if (event.type === 'tool/result') {
    state.questions.delete(d.message?.toolCallId);
  } else if (event.type === 'approval/asked') {
    state.approvals.add(d.id);
  } else if (event.type === 'approval/decided') {
    state.approvals.delete(d.id);
  }
}

export function agentMetadata(agent, projections, cursors) {
  const session = agent.session;
  let state = cursors.get(session);
  if (!state || state.seq > session.seq) {
    // Only the current turn can own foreground waits. Bound startup work.
    let start = session.seq;
    const floor = Math.max(session.firstLiveSeq ?? 0, session.seq - 10000);
    while (start > floor) {
      const event = session.eventAt(--start);
      if (event?.type === 'turn/start' || event?.type === 'turn/end') break;
    }
    state = {seq: start, questions: new Set(), approvals: new Set()};
    cursors.set(session, state);
  }
  // Process incrementally; only event type and opaque call IDs are retained.
  while (state.seq < session.seq) {
    foldEvent(state, session.eventAt(state.seq));
    // A failed read must be retried; advancing first can lose an approval.
    state.seq += 1;
  }
  const values = projections.snapshot(session, ['modelSelection', 'userQuestions']).values;
  const selection = values.modelSelection?.lastUsed ?? agent.options ?? {};
  const active = values.userQuestions?.active ?? [];
  const running = agent.status === 'running';
  // Timed questions remain active as `continued` after the tool returns and
  // work resumes. They still light the flower, but only `open` questions can
  // restore a foreground wait missing from the bounded event replay.
  const blockingQuestions = running
    ? Math.max(state.questions.size, active.filter(question => question.state === 'open').length)
    : 0;
  const approvals = running ? state.approvals.size : 0;
  const questions = Math.max(blockingQuestions, active.length);
  return {
    id: String(agent.id), running,
    effort: typeof selection.reasoningEffort === 'string' ? selection.reasoningEffort : null,
    model: typeof selection.model === 'string' ? selection.model : null,
    blocking: blockingQuestions + approvals > 0, questions, approvals,
  };
}

export function createObserver(scope, options = {}) {
  const root = options.root ?? join(homedir(), 'Library', 'Application Support', 'RotatingFlower', 'dsh');
  const tick = options.tick ?? TICK_MS;
  const heartbeat = options.heartbeat ?? HEARTBEAT_MS;
  const limit = options.limit ?? FAILURE_LIMIT;
  const file = join(root, 'status.json');
  const instance = randomUUID();
  const temporary = join(root, `status.${instance}.tmp`);
  const cursors = new WeakMap();
  let disposed = false;
  let failures = 0;
  let lastGood = null;
  let lastBody = null;
  let lastWrite = 0;
  let timer = null;
  const write = (final = false) => {
    if (disposed && !final) return;
    try {
      let tasks = [], error = null;
      if (!final) {
        try {
          tasks = scope.agents.list().map(a => agentMetadata(a, scope.sessionProjections, cursors));
          failures = 0; lastGood = tasks;
        } catch {
          // Hold the last good snapshot through a blip instead of blinking the
          // flower; report only after the runtime stays unreadable.
          failures += 1;
          error = failures >= limit ? 'unsupported_task_metadata' : null;
          tasks = error ? [] : (lastGood ?? []);
        }
      }
      const connected = !final && error === null;
      const body = JSON.stringify({schema: 1, instance, pid: process.pid, connected, error, tasks});
      const now = Date.now();
      // Only a changed snapshot is written immediately; an unchanged one still
      // refreshes updated_at once per heartbeat so the bridge can tell a quiet
      // DSH from a dead one.
      if (!final && body === lastBody && now - lastWrite < heartbeat) return;
      mkdirSync(root, {recursive: true, mode: 0o700});
      writeFileSync(temporary, JSON.stringify({schema: 1, instance, pid: process.pid,
        updated_at: now / 1000, connected, error, tasks}), {mode: 0o600});
      renameSync(temporary, file);
      lastBody = body; lastWrite = now;
    } catch { /* Observability must never disrupt DSH or change its decisions. */ }
  };
  const stop = () => {
    if (timer) clearInterval(timer);
    timer = null; disposed = true; write(true);
  };
  const start = () => {
    write();
    timer = setInterval(() => write(), tick);
    timer.unref?.();
    return stop;
  };
  return {file, write, start, stop};
}

export default function flowerObserver(ctx) {
  ctx.inject(['agents', 'sessionProjections'], (scope) => {
    scope.effect(() => createObserver(scope).start(), 'rotating-flower metadata heartbeat');
  });
}
