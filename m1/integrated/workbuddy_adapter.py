"""Read WorkBuddy task/worker and task-notifier metadata, never chat bodies.

5.9.3 persists a lossy `pending` status for both idle and blocked tasks. The
daemon's task-notifier metadata supplies the missing question/permission kind.
Only a current DB pending state, matching transition and live worker light the
flower. These are private app formats: unknown data fails quiet.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from contextlib import closing
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time

RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "XHIGH": 4, "ULTRA": 5}
WORKING = frozenset(("working", "planning"))
WAITING = frozenset(("pending", "waiting_permission"))
TERMINAL = frozenset(("completed", "failed", "error", "terminated", "archived"))
NOTIFIER = re.compile(r"^\[TaskStatusNotifier\] upsert received: session=([\w-]+) "
                      r"prev=([\w<>-]+) new=([\w-]+) kind=([\w<>-]+)$")
KINDS = frozenset(("question", "permission", "user_input"))


def speed_for_model(model):
    if not isinstance(model, str) or not model.strip():
        return "LOW"
    return {"fast-model": "LOW", "balanced-model": "HIGH", "deep-model": "ULTRA"}.get(model.strip(), "HIGH")


def stamp(value):
    try:
        value = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        return value if math.isfinite(value) else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class TaskEvent:
    timestamp: float
    status: str
    kind: str | None = None
    previous: str | None = None


class NotifierEvents:
    # Bounded startup scan and incremental tail. Rotated files are read first.
    MAX_SCAN = 16 * 1024 * 1024
    MAX_LINE = 64 * 1024

    def __init__(self, root):
        self.root = Path(root)
        self.cursors = {}
        self.latest = {}
        self.terminal_at = {}
        self.error = None

    def _line(self, line, now):
        # Ignore all other log entries before decoding JSON. No question,
        # command, token, title or answer is retained, parsed or logged.
        if b'[TaskStatusNotifier] upsert received:' not in line:
            return
        try:
            record = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(record, dict) or record.get("scope") != "daemon-server:task-notify":
            return
        at = stamp(record.get("timestamp"))
        if at is None or at > now + 2:
            return
        messages = record.get("message")
        if not isinstance(messages, list):
            return
        for message in messages:
            match = NOTIFIER.fullmatch(message) if isinstance(message, str) else None
            if not match:
                continue
            sid, previous, status, kind = match.groups()
            event = TaskEvent(at, status, kind if kind in KINDS else None, previous)
            old = self.latest.get(sid)
            # A terminal wins ties; duplicated/late old events cannot revive it.
            if old is None or (at, status in TERMINAL) > (old.timestamp, old.status in TERMINAL):
                self.latest[sid] = event
            if status in TERMINAL:
                self.terminal_at[sid] = max(at, self.terminal_at.get(sid, 0))

    def poll(self, now):
        self.error = None
        for name in ("daemon.old.log", "daemon.log"):
            path = self.root / "logs" / name
            try:
                with path.open("rb") as file:
                    stat = os.fstat(file.fileno())
                    identity = (stat.st_dev, stat.st_ino)
                    cursor = self.cursors.get(name)
                    reset = not cursor or cursor[0] != identity or stat.st_size < cursor[1]
                    if reset:
                        offset = max(0, stat.st_size - self.MAX_SCAN)
                        pending = b""
                        dropping = offset > 0
                    else:
                        _, offset, pending, dropping = cursor
                    file.seek(offset)
                    data = file.read(self.MAX_SCAN)
                    offset += len(data)
                    for part in data.splitlines(keepends=True):
                        if dropping:
                            if part.endswith(b'\n'):
                                dropping = False
                            continue
                        pending += part
                        if len(pending) > self.MAX_LINE:
                            dropping = not part.endswith(b'\n')
                            pending = b""
                        elif pending.endswith(b'\n'):
                            self._line(pending, now)
                            pending = b""
                    self.cursors[name] = (identity, offset, pending, dropping)
            except FileNotFoundError:
                self.cursors.pop(name, None)
                if name == 'daemon.log':
                    self.error = 'WorkBuddy task notification log is missing; waiting-state detection unavailable'
            except OSError:
                self.error = "WorkBuddy task notification metadata is not readable"


@dataclass
class SdkTurn:
    instance: str
    last_at: float = 0
    started_at: float = 0
    status: str | None = None
    status_at: float = 0
    request: str | None = None
    activity_at: float = 0


class SdkActivity:
    """Optional active-turn metadata, not model output or conversation text.

    Observed 5.9.3 emits session_info_update every 60 seconds even during a
    long tool invocation. This is useful only with a live interactive worker,
    its matching registration identity and the same request/turn. Registration
    lastHeartbeat can remain at startup even for a healthy interactive worker.
    """
    MAX_SCAN = 2 * 1024 * 1024
    MAX_LINE = 64 * 1024

    def __init__(self, root):
        self.root = Path(root)
        self.cursors = {}
        self.turns = {}

    def _line(self, line, sid, now):
        try:
            raw_at, event, raw_json = line.split(b' ', 2)
            if event not in (b'state-machine:transition', b'runtime-status:persisted', b'event-machine:dispatch'):
                return
            # Dispatch has other event types too. Reject them before decoding
            # their payload, which may contain model/user content.
            if (event == b'event-machine:dispatch'
                    and not re.search(rb'"input"\s*:\s*"session_info_update"', raw_json)):
                return
            at = stamp(raw_at.decode('ascii'))
            if at is None or at > now + 2:
                return
            data = json.loads(raw_json)
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(data, dict) or data.get('conversationId') != sid:
            return
        instance = data.get('instanceId')
        if not isinstance(instance, str) or not instance:
            return
        old = self.turns.get(sid)
        if old and at < old.last_at:
            return
        state = old if old and old.instance == instance else SdkTurn(instance)
        state.last_at = at
        self.turns[sid] = state
        if event == b'state-machine:transition' and data.get('valid') is True:
            if data.get('input') == 'PROMPT_SENT':
                state.started_at = at
                state.request = None
                state.activity_at = 0
            to = data.get('to')
            if to in WORKING | WAITING | TERMINAL | {'idle'}:
                state.status, state.status_at = to, at
        elif event == b'runtime-status:persisted':
            status = data.get('status')
            if status in WORKING | WAITING | TERMINAL | {'idle'}:
                state.status, state.status_at = status, at
        elif (event == b'event-machine:dispatch' and data.get('input') == 'session_info_update'
              and state.started_at and state.status in WORKING):
            request = data.get('requestId')
            if isinstance(request, str) and request:
                if state.request is None:
                    state.request = request
                if state.request == request:
                    state.activity_at = at

    def poll(self, sessions, now):
        # Current/previous daily logs cover crossing midnight without retaining
        # every historical conversation. A missing turn start fails quiet.
        days = sorted(p for p in (self.root / 'logs').glob('????-??-??') if p.is_dir())[-2:]
        keep = set()
        for sid in sessions:
            if not isinstance(sid, str) or not re.fullmatch(r'[\w-]+', sid):
                continue
            for day in days:
                path = day / 'sdk/conversations' / (sid + '.log')
                keep.add(path)
                try:
                    with path.open('rb') as file:
                        stat = os.fstat(file.fileno())
                        identity = (stat.st_dev, stat.st_ino)
                        old = self.cursors.get(path)
                        if not old or old[0] != identity or stat.st_size < old[1]:
                            offset = max(0, stat.st_size-self.MAX_SCAN)
                            pending = b''
                            dropping = offset > 0
                        else:
                            _, offset, pending, dropping = old
                        file.seek(offset)
                        data = file.read(self.MAX_SCAN)
                        offset += len(data)
                        for part in data.splitlines(keepends=True):
                            if dropping:
                                if part.endswith(b'\n'):dropping=False
                                continue
                            pending += part
                            if len(pending)>self.MAX_LINE:
                                dropping=not part.endswith(b'\n');pending=b''
                            elif pending.endswith(b'\n'):
                                self._line(pending,sid,now);pending=b''
                        self.cursors[path]=(identity,offset,pending,dropping)
                except OSError:
                    self.cursors.pop(path,None)
        self.cursors={k:v for k,v in self.cursors.items() if k in keep}
        self.turns={k:v for k,v in self.turns.items() if k in sessions}

    def matches_workers(self, state, workers, metadata):
        for identity in workers:
            record = metadata.get(identity, {})
            start = record.get('startedAt')
            if (record.get('kind') == 'interactive' and type(start) in (int,float)
                    and math.isfinite(start) and 0 < start/1000 <= state.started_at+2):
                yield record

    def blocks(self, sid, updated, workers, metadata):
        state=self.turns.get(sid)
        return bool(state and state.started_at and state.status in WAITING | TERMINAL | {'idle'}
                    # DB/log writes of adjacent turns can differ by a few ms.
                    # A previous terminal must not stop a newly started turn.
                    and state.status_at > updated+.01
                    and any(self.matches_workers(state,workers,metadata)))

    def fresh_work(self, sid, updated, workers, metadata, now):
        state=self.turns.get(sid)
        if (not state or state.status not in WORKING or not state.request
                or state.activity_at < updated or not -2 <= now-state.activity_at <= 90):
            return None
        return state.activity_at if any(self.matches_workers(state,workers,metadata)) else None


class WorkBuddyAdapter:
    def __init__(self, root, stale_seconds=600, transition_tolerance=10):
        self.root = Path(root)
        self.stale_seconds = stale_seconds
        self.transition_tolerance = transition_tolerance
        self.events = NotifierEvents(root)
        self.sdk = SdkActivity(root)
        self.latched = {}
        self.worker_metadata = {}
        self._probe_denied = False

    def _workers(self):
        live = {}
        self.worker_metadata = {}
        self._probe_denied = False
        for path in (self.root / 'sessions').glob('*.json'):
            if not path.stem.isdecimal():
                continue
            try:
                if path.stat().st_size > 65536:
                    continue
                data = json.loads(path.read_bytes())
                if not isinstance(data, dict) or data.get('kind') == 'prewarm':
                    continue
                pid, sid = data.get('pid'), data.get('sessionId')
                if type(pid) is not int or pid <= 0 or str(pid) != path.stem or not isinstance(sid, str) or not sid:
                    continue
                os.kill(pid, 0)
                started = data.get('startedAt')
                if not isinstance(started, (str, int, float)):
                    started = None
                live.setdefault(sid, set()).add((pid, started))
                self.worker_metadata[(pid, started)] = {key:data.get(key) for key in ('kind','startedAt')}
            except PermissionError:
                self._probe_denied = True
            except (OSError, ValueError):
                continue
        return {sid: frozenset(workers) for sid, workers in live.items()}

    def poll(self, now=None):
        now = time.time() if now is None else now
        empty = {'healthy': False, 'error': None, 'readiness': 'error', 'motor': 'STOP', 'light': False,
                 'working_threads': [], 'waiting_threads': [], 'pending_questions': 0,
                 'waiting_kinds': {}, 'degraded_threads': []}
        try:
            # Missing first-use metadata is expected on a newly installed app.
            # Re-check every poll so opening WorkBuddy requires no reinstall.
            database = (self.root / 'workbuddy.db').resolve()
            try:
                database.stat()
            except FileNotFoundError:
                self.latched.clear()
                return {**empty, 'readiness': 'not_initialized',
                        'detail': '打开并登录 WorkBuddy，开始一次任务后会自动联动。'}
            self.events.poll(now)
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=.2)) as connection:
                connection.execute('PRAGMA query_only=ON')
                columns = {r[1] for r in connection.execute('PRAGMA table_info(sessions)')}
                model = 'model' if 'model' in columns else 'NULL'
                rows = connection.execute(f'SELECT id,status,updated_at,{model} FROM sessions '
                                          "WHERE transport='local' AND deleted_at IS NULL").fetchall()
            live = self._workers()
            self.sdk.poll(live, now)
        except (OSError, sqlite3.Error, ValueError):
            self.latched.clear()
            return {**empty, 'error': 'WorkBuddy task metadata unavailable or incompatible'}

        working, waiting, kinds, degraded, keep = {}, [], {}, [], {}
        for sid, status, updated_at, model in rows:
            if not isinstance(sid, str) or not isinstance(status, str):
                continue
            status = status.lower()
            if status not in WORKING | WAITING or sid not in live:
                continue
            if type(updated_at) not in (int, float):
                continue
            updated = updated_at / 1000
            if not math.isfinite(updated) or updated > now + 2:
                degraded.append(sid)
                continue
            event = self.events.latest.get(sid)
            latched = self.latched.get(sid)
            # Terminal log events catch a finished/new turn between DB polls.
            if latched and (latched[0] != live[sid] or self.events.terminal_at.get(sid, 0) > latched[2]):
                latched = None
            speed = latched[1] if latched else speed_for_model(model)
            since = latched[2] if latched else now

            if status in WAITING:
                # Pending alone also means a new, idle session. Require a
                # matching transition, even when bootstrapping after restart.
                valid = bool(event and event.status in WAITING and event.kind in KINDS
                             and abs(event.timestamp - updated) <= self.transition_tolerance)
                if valid:
                    waiting.append(sid)
                    kinds[sid] = event.kind
                    keep[sid] = (live[sid], speed, since)
                else:
                    degraded.append(sid)
                continue

            if self.sdk.blocks(sid,updated,live[sid],self.worker_metadata):
                degraded.append(sid)
                continue
            if event and event.status in TERMINAL and event.timestamp > updated+.01:
                degraded.append(sid)
                continue
            # Fresh SDK activity for this request and a matching live worker
            # can extend long work. A live PID alone never suffices.
            evidence = updated
            if event and event.timestamp >= updated and event.status in WORKING:
                evidence = event.timestamp
            active_request = self.sdk.fresh_work(sid,updated,live[sid],self.worker_metadata,now)
            if now - evidence > self.stale_seconds and active_request is None:
                degraded.append(sid)
                continue
            working[sid] = speed
            keep[sid] = (live[sid], speed, since)

        self.latched = keep
        # Prune metadata to existing DB sessions; avoid unbounded history.
        ids = {row[0] for row in rows}
        self.events.latest = {k:v for k,v in self.events.latest.items() if k in ids}
        self.events.terminal_at = {k:v for k,v in self.events.terminal_at.items() if k in ids}
        error = self.events.error
        if self._probe_denied:
            error = 'WorkBuddy worker verification denied; unverified tasks ignored'
        if error:
            return {**empty, 'error': error, 'degraded_threads': sorted(set(working) | set(waiting) | set(degraded))}
        return {'healthy': True, 'error': error, 'readiness': 'ready',
                'motor': 'RUN ' + max(working.values(), key=RANK.get) if working else 'STOP',
                'light': bool(waiting), 'working_threads': sorted(working),
                'waiting_threads': sorted(waiting), 'pending_questions': len(waiting),
                'waiting_kinds': kinds, 'degraded_threads': sorted(degraded)}

    def close(self):
        self.latched.clear()
