"""Read-only observer of Qoder CN local session transcripts.

Qoder CN appends one internal JSONL transcript per local session under
~/.qoder-cn/projects/<workspace>/<session-id>.jsonl while a turn runs. This
adapter keeps only task-state flags, the selected model/effort and timestamps:
no prompt, tool argument, tool output or message text is stored or logged.
The transcript format is internal and may change; retest after Qoder updates.

Attention is derived from a pending AskUserQuestion tool call. Permission
prompts are not visible in the transcript, so an approval wait shows up as
ordinary work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.parse import unquote

try:
    from platform_support import open_read_shared
except ImportError:  # macOS package has no platform_support module.
    def open_read_shared(path):
        return Path(path).open('rb')

RANK = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'XHIGH': 4, 'ULTRA': 5}
EFFORT_SPEED = {'off': 'LOW', 'none': 'LOW', 'minimal': 'LOW', 'low': 'LOW', 'medium': 'MEDIUM',
                'high': 'HIGH', 'xhigh': 'XHIGH', 'max': 'ULTRA', 'ultra': 'ULTRA'}
QUESTION_TOOLS = frozenset(('AskUserQuestion',))
TERMINAL_STOPS = frozenset(('end_turn', 'stop_sequence', 'max_tokens'))
INTERRUPTED_PREFIX = '[Request interrupted'


def speed_for_effort(effort):
    if not isinstance(effort, str):
        return None
    return EFFORT_SPEED.get(effort.strip().lower())


def model_key(model):
    """Normalize 'byok:provider%2Fmodel' and 'provider/model' to one key."""
    if not isinstance(model, str) or not model.strip():
        return None
    value = model.strip()
    if value.startswith('byok:'):
        value = value[5:]
    return unquote(value)


def speed_for_state(state, catalog=None, log_effort=None):
    speed = speed_for_effort(state.effort)
    if speed is None:
        speed = speed_for_effort(log_effort)
    if speed is None and state.model and catalog is not None:
        speed = speed_for_effort(catalog.effort(state.model))
    return speed or 'MEDIUM'


def app_data_candidates():
    candidates = []
    appdata = os.environ.get('APPDATA')
    if appdata:
        candidates.append(Path(appdata) / 'com.qodercn.app.stable')
    candidates.extend([Path.home() / 'Library/Application Support/QoderCN',
                       Path.home() / 'Library/Application Support/Qoder CN',
                       Path.home() / 'Library/Application Support/com.qodercn.app.stable',
                       Path.home() / '.config/QoderCN'])
    return candidates


class ModelEffortCatalog:
    """Optional read of Qoder's model preference table; unknown data fails quiet.

    The app database only supplies the model's configured reasoning effort, so
    a missing or changed schema degrades to the neutral MEDIUM speed.
    """
    REFRESH = 60.0

    def __init__(self, app_data=None):
        self.explicit = Path(app_data) if app_data else None
        self.efforts = {}
        self.loaded_at = None
        self.path = None

    def database(self):
        if self.explicit is not None:
            return self.explicit / 'main.sqlite' if self.explicit.name != 'main.sqlite' else self.explicit
        for root in app_data_candidates():
            if root is None:
                continue
            database = root / 'main.sqlite'
            try:
                if database.is_file():
                    return database
            except OSError:
                continue
        return None

    def refresh(self, now=None):
        now = time.monotonic() if now is None else now
        if self.loaded_at is not None and now - self.loaded_at < self.REFRESH:
            return
        self.loaded_at = now
        self.efforts = {}
        database = self.database()
        if database is None:
            return
        connection = None
        try:
            connection = sqlite3.connect(database.resolve().as_uri() + '?mode=ro',
                                         uri=True, timeout=0.2)
            connection.execute('PRAGMA query_only = ON')
            rows = connection.execute(
                'SELECT model_key, reasoning_effort FROM chat_model_preferences').fetchall()
            efforts = {}
            for key, effort in rows:
                normalized = model_key(key)
                if normalized and isinstance(effort, str) and effort.strip():
                    efforts[normalized] = effort
            self.efforts = efforts
            self.path = database
        except (OSError, sqlite3.Error):
            pass
        finally:
            if connection is not None:
                connection.close()

    def effort(self, model):
        key = model_key(model)
        if key is None:
            return None
        self.refresh()
        return self.efforts.get(key)


@dataclass
class SessionState:
    session_id: str
    phase: str = 'idle'
    model: str | None = None
    effort: str | None = None
    questions: int = 0
    message_id: str | None = None
    pending_tools: list = field(default_factory=list)

    def record(self, record):
        kind = record.get('type')
        if kind == 'runtime-config':
            if isinstance(record.get('model'), str):
                self.model = record['model']
            effort = record.get('reasoningEffort')
            self.effort = effort if isinstance(effort, str) and effort.strip() else None
            return
        if record.get('isSidechain') is True:
            return
        message = record.get('message')
        if not isinstance(message, dict):
            return
        content = message.get('content')
        blocks = content if isinstance(content, list) else []
        if kind == 'assistant':
            if isinstance(message.get('model'), str):
                self.model = message['model']
            message_id = message.get('id')
            if message_id != self.message_id:
                self.message_id = message_id
                self.pending_tools = []
            for block in blocks:
                if isinstance(block, dict) and block.get('type') == 'tool_use':
                    name = block.get('name')
                    if isinstance(name, str):
                        self.pending_tools.append(name)
            stop = message.get('stop_reason')
            if stop is None:
                self.phase = 'working'
            elif stop == 'tool_use':
                if any(name in QUESTION_TOOLS for name in self.pending_tools):
                    self.phase = 'waiting'
                    self.questions = 1
                else:
                    self.phase = 'working'
                    self.questions = 0
            else:
                # end_turn/stop_sequence/max_tokens and unknown terminal values.
                self.phase = 'idle'
                self.questions = 0
        elif kind == 'user':
            self.message_id = None
            self.pending_tools = []
            interrupted = any(isinstance(block, dict) and block.get('type') == 'text'
                              and isinstance(block.get('text'), str)
                              and block['text'].startswith(INTERRUPTED_PREFIX)
                              for block in blocks)
            self.phase = 'idle' if interrupted else 'working'
            self.questions = 0


class AppLogEffort:
    """Read the per-turn reasoning effort Qoder freezes into its main log.

    The session transcript records reasoningEffort as null, and the model
    preference table only holds a static default. The desktop app instead
    logs `ChatSession model policy ... {"frozenReasoningEffort":"max"}` for
    each session when it sends a turn. Only that one field is kept.
    """
    MAX_SCAN = 4 * 1024 * 1024
    MAX_LINE = 256 * 1024

    def __init__(self, app_data=None):
        self.app_data = Path(app_data) if app_data else None
        self.cursors = {}
        self.efforts = {}

    def log_root(self):
        # An explicit app-data directory is authoritative, which keeps tests
        # and unusual installs from borrowing logs from the default location.
        if self.app_data is not None:
            root = self.app_data.parent if self.app_data.name == 'main.sqlite' else self.app_data
            return root / 'logs' if (root / 'logs').is_dir() else None
        for root in app_data_candidates():
            try:
                if (root / 'logs').is_dir():
                    return root / 'logs'
            except OSError:
                continue
        return None

    def poll(self, now):
        root = self.log_root()
        if root is None:
            self.efforts = {}
            return
        try:
            logs = []
            for run in root.iterdir():
                try:
                    # Rotation renames the active file (main.1.log) and starts
                    # a fresh main.log; oldest-first makes the newest line win.
                    for path in run.glob('main*.log'):
                        logs.append((path.stat().st_mtime, path))
                except OSError:
                    continue
            logs.sort()
        except OSError:
            return
        keep = set()
        for _, path in logs[-6:]:
            keep.add(path)
            self._tail(path)
        self.cursors = {k: v for k, v in self.cursors.items() if k in keep}

    def _tail(self, path):
        try:
            with open_read_shared(path) as file:
                stat = os.fstat(file.fileno())
                identity = (stat.st_dev, stat.st_ino)
                cursor = self.cursors.get(path)
                if not cursor or cursor[0] != identity or stat.st_size < cursor[1]:
                    offset = max(0, stat.st_size - self.MAX_SCAN)
                    pending, dropping = b'', offset > 0
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
                        pending = b''
                    elif pending.endswith(b'\n'):
                        self._line(pending)
                        pending = b''
                self.cursors[path] = (identity, offset, pending, dropping)
        except OSError:
            self.cursors.pop(path, None)

    def _line(self, line):
        if b'ChatSession model policy' not in line or b'frozenReasoningEffort' not in line:
            return
        start = line.find(b'{')
        if start < 0:
            return
        try:
            body = json.loads(line[start:].decode('utf-8', 'replace'))
        except ValueError:
            return
        session_id = body.get('sessionId')
        effort = body.get('frozenReasoningEffort')
        if isinstance(session_id, str) and isinstance(effort, str):
            self.efforts[session_id] = effort


class TranscriptFile:
    """Incremental tail reader; startup scans only the newest bounded window."""
    INITIAL_SCAN = 4 * 1024 * 1024
    CHUNK = 256 * 1024
    MAX_LINE = 1024 * 1024

    def __init__(self, path):
        self.path = Path(path)
        self.state = SessionState(self.path.stem)
        self.file = None
        self.identity = None
        self.offset = 0
        self.pending = b''
        self.dropping = False
        self.mtime = 0.0
        with self.path.open('rb') as file:
            stat = os.fstat(file.fileno())
            self.identity = (stat.st_dev, stat.st_ino)
            self.mtime = stat.st_mtime
            start = max(0, stat.st_size - self.INITIAL_SCAN)
            self.offset = start
            self.dropping = start > 0
            file.seek(start)
            self._read(file, stat.st_size)

    @staticmethod
    def kind(line):
        # Reject bulky bookkeeping records (file snapshots) before decoding.
        head = line[:64]
        for name in (b'assistant', b'user', b'runtime-config'):
            if b'"type":"' + name + b'"' in head or b'"type": "' + name + b'"' in head:
                return name
        return None

    def _consume(self, line):
        kind = self.kind(line)
        if kind is None:
            return
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, ValueError):
            return
        if isinstance(record, dict):
            self.state.record(record)

    def _read(self, file, size):
        while self.offset < size:
            chunk = file.read(min(self.CHUNK, size - self.offset))
            if not chunk:
                break
            self.offset += len(chunk)
            data = self.pending + chunk
            parts = data.split(b'\n')
            self.pending = parts.pop()
            for line in parts:
                if self.dropping:
                    self.dropping = False
                    continue
                if line:
                    self._consume(line)
            if len(self.pending) > self.MAX_LINE:
                self.pending = b''
                self.dropping = True

    def poll(self):
        try:
            with self.path.open('rb') as file:
                stat = os.fstat(file.fileno())
                identity = (stat.st_dev, stat.st_ino)
                self.mtime = stat.st_mtime
                if identity != self.identity or stat.st_size < self.offset:
                    # Rewritten/compacted transcript: rebuild from the new tail.
                    self.state = SessionState(self.path.stem)
                    self.identity = identity
                    self.offset = 0
                    self.pending = b''
                    start = max(0, stat.st_size - self.INITIAL_SCAN)
                    self.offset = start
                    self.dropping = start > 0
                    file.seek(start)
                else:
                    file.seek(self.offset)
                self._read(file, stat.st_size)
        except OSError:
            raise

    def close(self):
        pass


class QoderCnSource:
    """One snapshot per poll in the same shape as the other bridge sources."""
    MAX_SESSIONS = 512

    def __init__(self, root=None, app_data=None, stale_seconds=600):
        self.root = Path(root) if root is not None else Path.home() / '.qoder-cn'
        self.projects = self.root / 'projects'
        self.stale_seconds = stale_seconds
        self.catalog = ModelEffortCatalog(app_data)
        self.effort_log = AppLogEffort(app_data)
        self.sessions = {}

    def quiet(self, readiness, detail=None, error=None):
        return {'healthy': False, 'error': error, 'readiness': readiness,
                'detail': detail, 'motor': 'STOP', 'light': False,
                'working_threads': [], 'waiting_threads': [], 'pending_questions': 0}

    def _discover(self, now):
        recent = {}
        try:
            for path in self.projects.glob('*/*.jsonl'):
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if -2 <= now - mtime <= self.stale_seconds:
                    recent[path] = mtime
        except OSError:
            return None
        if len(recent) > self.MAX_SESSIONS:
            recent = dict(sorted(recent.items(), key=lambda item: item[1], reverse=True)
                          [:self.MAX_SESSIONS])
        return recent

    def poll(self, now=None):
        now = time.time() if now is None else now
        try:
            root_stat = self.root.stat()
        except FileNotFoundError:
            return self.quiet('not_initialized', '打开并登录 Qoder CN，开始一次任务后会自动联动。')
        except OSError:
            return self.quiet('error', error='Qoder CN 数据目录不可读取')
        if self.projects.exists() and not self.projects.is_dir():
            return self.quiet('error', error='Qoder CN 任务目录不是文件夹')
        if not self.projects.is_dir():
            return self.quiet('not_initialized', '在 Qoder CN 开始一次任务后会自动联动。')

        recent = self._discover(now)
        if recent is None:
            return self.quiet('error', error='Qoder CN 任务目录不可读取')
        self.effort_log.poll(now)

        for path in list(self.sessions):
            if path not in recent:
                del self.sessions[path]
        working, waiting, speeds, pending = [], [], {}, 0
        for path in recent:
            entry = self.sessions.get(path)
            if entry is None:
                try:
                    entry = TranscriptFile(path)
                except OSError:
                    continue
                self.sessions[path] = entry
            else:
                try:
                    entry.poll()
                except OSError:
                    del self.sessions[path]
                    continue
            state = entry.state
            session_id = state.session_id
            if state.phase == 'working':
                working.append(session_id)
                speeds[session_id] = speed_for_state(
                    state, self.catalog, self.effort_log.efforts.get(session_id))
            elif state.phase == 'waiting':
                waiting.append(session_id)
                pending += state.questions
        self.effort_log.efforts = {
            key: value for key, value in self.effort_log.efforts.items()
            if any(entry.state.session_id == key for entry in self.sessions.values())}

        motor = 'STOP'
        if speeds:
            motor = 'RUN ' + max(speeds.values(), key=RANK.get)
        return {'healthy': True, 'error': None, 'readiness': 'ready', 'detail': None,
                'motor': motor, 'light': bool(waiting),
                'working_threads': sorted(working), 'waiting_threads': sorted(waiting),
                'pending_questions': pending}

    def close(self):
        for entry in self.sessions.values():
            entry.close()
        self.sessions.clear()