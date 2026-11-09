import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { foldEvent, agentMetadata, createObserver } from './flower-observer.mjs';

function session(events) {
  return {
    seq: events.length,
    firstLiveSeq: 0,
    eventAt(index) { return events[index]; },
  };
}

function agent(events, {id = 'session-a', status = 'running', options = undefined} = {}) {
  return {id, status, options, session: session(events)};
}

function projections({model, active = []} = {}) {
  return {
    snapshot: () => ({values: {
      modelSelection: model ? {lastUsed: model} : undefined,
      userQuestions: {active},
    }}),
  };
}

const question = callId => ({type: 'tool/call', data: {name: 'ask_user_question', callId}});
const answer = callId => ({type: 'tool/result', data: {message: {toolCallId: callId}}});

test('a pending question blocks the task', () => {
  const meta = agentMetadata(agent([{type: 'turn/start'}, question('c1')]), projections(), new WeakMap());
  assert.equal(meta.questions, 1);
  assert.equal(meta.blocking, true);
});

test('answering the question clears the wait', () => {
  const events = [{type: 'turn/start'}, question('c1'), answer('c1')];
  const meta = agentMetadata(agent(events), projections(), new WeakMap());
  assert.equal(meta.questions, 0);
  assert.equal(meta.blocking, false);
});

test('an approval blocks until it is decided', () => {
  const cursors = new WeakMap();
  const events = [{type: 'turn/start'}, {type: 'approval/asked', data: {id: 'a1', callId: 'c1'}}];
  const first = agentMetadata(agent(events), projections(), cursors);
  assert.equal(first.approvals, 1);
  assert.equal(first.blocking, true);
  events.push({type: 'approval/decided', data: {id: 'a1', outcome: 'accepted'}});
  const second = agentMetadata(agent(events), projections(), cursors);
  assert.equal(second.approvals, 0);
  assert.equal(second.blocking, false);
});

test('a new turn clears waits left over from the previous one', () => {
  const events = [{type: 'turn/start'}, question('c1'), {type: 'turn/end'}, {type: 'turn/start'}];
  const meta = agentMetadata(agent(events), projections(), new WeakMap());
  assert.equal(meta.questions, 0);
  assert.equal(meta.blocking, false);
});

test('an open projected question blocks even without a matching event', () => {
  const meta = agentMetadata(agent([{type: 'turn/start'}]),
    projections({active: [{callId: 'q1', state: 'open'}]}), new WeakMap());
  assert.equal(meta.questions, 1);
  assert.equal(meta.blocking, true);
});

test('a timed-out question keeps attention while the task resumes work', () => {
  const events = [{type: 'turn/start'}, question('c1')];
  const target = agent(events);
  const cursors = new WeakMap();
  assert.equal(agentMetadata(target, projections(), cursors).blocking, true);
  events.push(answer('c1'));
  target.session.seq = events.length;
  const meta = agentMetadata(target,
    projections({active: [{callId: 'c1', state: 'continued'}]}), cursors);
  assert.equal(meta.running, true);
  assert.equal(meta.questions, 1);
  assert.equal(meta.blocking, false);
  assert.equal(agentMetadata(target, projections(), cursors).questions, 0);
});

test('a continued projected question does not block startup without its events', () => {
  const meta = agentMetadata(agent([{type: 'turn/start'}]),
    projections({active: [{callId: 'q1', state: 'continued'}]}), new WeakMap());
  assert.equal(meta.questions, 1);
  assert.equal(meta.blocking, false);
});

test('an open question still blocks alongside a continued question', () => {
  const meta = agentMetadata(agent([{type: 'turn/start'}]), projections({active: [
    {callId: 'q1', state: 'continued'}, {callId: 'q2', state: 'open'},
  ]}), new WeakMap());
  assert.equal(meta.questions, 2);
  assert.equal(meta.blocking, true);
});

test('a task that is not running reports no foreground wait', () => {
  const events = [{type: 'turn/start'}, question('c1'), {type: 'approval/asked', data: {id: 'a1'}}];
  const meta = agentMetadata(agent(events, {status: 'idle'}), projections(), new WeakMap());
  assert.equal(meta.questions, 0);
  assert.equal(meta.approvals, 0);
  assert.equal(meta.blocking, false);
  assert.equal(meta.running, false);
});

test('later events are folded incrementally without replaying the session', () => {
  const events = [{type: 'turn/start'}];
  const target = agent(events);
  const cursors = new WeakMap();
  assert.equal(agentMetadata(target, projections(), cursors).questions, 0);
  events.push(question('c2'));
  target.session.seq = events.length;
  assert.equal(agentMetadata(target, projections(), cursors).questions, 1);
});

test('turn boundaries clear waits when the same session is polled again', () => {
  const events = [{type: 'turn/start'}, question('c1'),
    {type: 'approval/asked', data: {id: 'a1'}}];
  const target = agent(events);
  const cursors = new WeakMap();
  assert.equal(agentMetadata(target, projections(), cursors).blocking, true);
  events.push({type: 'turn/end'}, {type: 'turn/start'});
  target.session.seq = events.length;
  const meta = agentMetadata(target, projections(), cursors);
  assert.equal(meta.questions, 0);
  assert.equal(meta.approvals, 0);
  assert.equal(meta.blocking, false);
});

test('a compacted session replays from the last turn boundary', () => {
  const target = agent([{type: 'turn/start'}, question('c1')]);
  const cursors = new WeakMap();
  const first = agentMetadata(target, projections(), cursors);
  assert.equal(first.questions, 1);
  target.session = session([{type: 'turn/start'}, question('c9')]);
  cursors.set(target.session, {seq: 99, questions: new Set(), approvals: new Set()});
  const replayed = agentMetadata(target, projections(), cursors);
  assert.equal(replayed.questions, 1);
});

test('effort and model fall back to the agent options', () => {
  const meta = agentMetadata(
    agent([], {options: {reasoningEffort: 'max', model: 'deepseek-flash'}}),
    projections(), new WeakMap());
  assert.equal(meta.effort, 'max');
  assert.equal(meta.model, 'deepseek-flash');
  assert.equal(meta.id, 'session-a');
});

test('a projection wins over the agent options', () => {
  const meta = agentMetadata(
    agent([], {options: {reasoningEffort: 'low', model: 'old'}}),
    projections({model: {reasoningEffort: 'high', model: 'new'}}), new WeakMap());
  assert.equal(meta.effort, 'high');
  assert.equal(meta.model, 'new');
});

test('unknown effort types are reported as null, never as a guess', () => {
  const meta = agentMetadata(
    agent([], {options: {reasoningEffort: 4, model: 7}}), projections(), new WeakMap());
  assert.equal(meta.effort, null);
  assert.equal(meta.model, null);
});

test('a malformed event is ignored instead of throwing', () => {
  const state = {questions: new Set(), approvals: new Set()};
  foldEvent(state, {type: 'tool/result'});
  foldEvent(state, {type: 'tool/call', data: {name: 'ask_user_question'}});
  assert.equal(state.questions.size, 1);
});

function scopeWith(agents, model = projections()) {
  const scope = {
    failures: 0,
    agents: {list() { if (scope.failures) throw new Error('unsupported'); return agents; }},
    sessionProjections: model,
  };
  return scope;
}

function read(file) {
  return JSON.parse(readFileSync(file, 'utf8'));
}

test('the observer writes a bounded snapshot next to the bridge', () => {
  const root = mkdtempSync(join(tmpdir(), 'flower observer '));
  const scope = scopeWith([agent([{type: 'turn/start'}, question('c1')])]);
  const observer = createObserver(scope, {root, heartbeat: 60_000});
  observer.write();
  const payload = read(observer.file);
  assert.equal(payload.schema, 1);
  assert.equal(payload.connected, true);
  assert.equal(payload.error, null);
  assert.equal(payload.tasks.length, 1);
  assert.equal(payload.tasks[0].questions, 1);
  assert.equal(statSync(observer.file).mode & 0o777, 0o600);
});

test('an unchanged snapshot is written only when the heartbeat is due', t => {
  let now = 1800000000000;
  t.mock.method(Date, 'now', () => now);
  const root = mkdtempSync(join(tmpdir(), 'flower observer '));
  const observer = createObserver(scopeWith([agent([])]), {root, heartbeat: 1000});
  observer.write();
  const first = read(observer.file);
  now += 500;
  observer.write();
  assert.equal(read(observer.file).updated_at, first.updated_at);
  now += 500;
  observer.write();
  assert.equal(read(observer.file).updated_at, first.updated_at + 1);
});

test('one failed read holds the last good snapshot', () => {
  const root = mkdtempSync(join(tmpdir(), 'flower observer '));
  const scope = scopeWith([agent([{type: 'turn/start'}])]);
  const observer = createObserver(scope, {root, heartbeat: 60_000, limit: 3});
  observer.write();
  scope.failures = 1;
  observer.write();
  const payload = read(observer.file);
  assert.equal(payload.connected, true);
  assert.equal(payload.error, null);
  assert.equal(payload.tasks.length, 1);
});

test('an approval event is retried after a transient read failure', () => {
  const root = mkdtempSync(join(tmpdir(), 'flower observer '));
  const events = [{type: 'turn/start'}];
  const target = agent(events);
  const observer = createObserver(scopeWith([target]), {root, heartbeat: 60_000});
  observer.write();
  events.push({type: 'approval/asked', data: {id: 'a1'}});
  target.session.seq = events.length;
  let failed = false;
  target.session.eventAt = index => {
    if (!failed && index === 1) {
      failed = true;
      throw new Error('transient event read failure');
    }
    return events[index];
  };
  observer.write();
  assert.equal(read(observer.file).connected, true);
  assert.equal(read(observer.file).tasks[0].approvals, 0);
  observer.write();
  const payload = read(observer.file);
  assert.equal(payload.connected, true);
  assert.equal(payload.tasks[0].approvals, 1);
  assert.equal(payload.tasks[0].blocking, true);
});

test('persistent read failures are reported and stop the flower', () => {
  const root = mkdtempSync(join(tmpdir(), 'flower observer '));
  const scope = scopeWith([agent([{type: 'turn/start'}])]);
  const observer = createObserver(scope, {root, heartbeat: 60_000, limit: 3});
  observer.write();
  scope.failures = 1;
  for (let i = 0; i < 3; i += 1) observer.write();
  const payload = read(observer.file);
  assert.equal(payload.connected, false);
  assert.equal(payload.error, 'unsupported_task_metadata');
  assert.deepEqual(payload.tasks, []);
});

test('recovery resets the failure counter', () => {
  const root = mkdtempSync(join(tmpdir(), 'flower observer '));
  const scope = scopeWith([agent([{type: 'turn/start'}])]);
  const observer = createObserver(scope, {root, heartbeat: 60_000, limit: 3});
  scope.failures = 1;
  observer.write();
  scope.failures = 0;
  observer.write();
  assert.equal(read(observer.file).connected, true);
  scope.failures = 1;
  observer.write();
  assert.equal(read(observer.file).connected, true);
});

test('stopping the observer tells the bridge DSH is gone', () => {
  const root = mkdtempSync(join(tmpdir(), 'flower observer '));
  const observer = createObserver(scopeWith([agent([])]), {root, heartbeat: 60_000});
  observer.start();
  observer.stop();
  const payload = read(observer.file);
  assert.equal(payload.connected, false);
  assert.deepEqual(payload.tasks, []);
});
