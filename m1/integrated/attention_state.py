"""Read structured Codex async questions from local user-chat rollout records.

This adapter uses an internal on-disk format, not a stable event subscription.
It supports request_user_input_async question cards, not system approvals.
Only event metadata is retained; question text and answer content are discarded.

There is deliberately no pending-question expiry. A first-install boundary keeps
historical unanswered cards from being rediscovered. A metadata-only atomic cache
preserves tracked cards and resolution tombstones across service restarts.
task_complete means the assistant's turn finished, NOT that a question was closed.
File rotation/disappearance is likewise not evidence of a dismissed question.
An authoritative UI adapter may call reconcile_open_questions() or close_chat().
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

_START = '<send_user_message_question_reply>'
_END = '</send_user_message_question_reply>'
_TOOL = 'request_user_input_async'
_MARKERS = (b'request_user_input_async', b'send_user_message_question_reply',
            b'task_started', b'turn_aborted', b'function_call_output', b'"role"')
_MAX_LINE = 8_000_000
_CACHE_VERSION = 1


def _direct_user_reply(payload):
    """Recognize actual typed/image input, excluding injected app context.

    User-selected policy: direct input acknowledges older async questions in
    this chat. Exact card submissions still resolve only their matching IDs.
    Server approvals are independent of this adapter.
    """
    content = payload.get('content', [])
    if not isinstance(content, list):
        return False
    if any(isinstance(p, dict) and isinstance(p.get('text'), str)
           and p['text'].strip().startswith(_START) for p in content):
        return False
    meta = payload.get('internal_chat_message_metadata_passthrough') or {}
    if not isinstance(meta, dict):
        return False
    kinds = meta.get('content_item_kinds') or []
    provenance = meta.get('content_item_metadata') or []
    genuine = (any(isinstance(k, str) and k.startswith('user.') for k in kinds)
               or any(isinstance(p, dict) and isinstance(p.get('provenance'), dict)
                      and p['provenance'].get('type') == 'user' for p in provenance))
    return genuine and any(isinstance(p, dict) and
        (p.get('type') in ('input_image', 'input_audio')
         or isinstance(p.get('text'), str) and bool(p['text'].strip())) for p in content)


def _valid_time(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _question_id(value) -> tuple[str, int] | None:
    """Accept exact UI questionItemId JSON or an already decoded ID tuple."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, (list, tuple)):
        return None
    if len(value) == 3 and value[0] == _TOOL:
        value = value[1:]
    if (len(value) != 2 or not isinstance(value[0], str) or not value[0]
            or type(value[1]) is not int or value[1] < 0):
        return None
    return value[0], value[1]


def _timestamp(record: dict) -> float | None:
    value = record.get('timestamp')
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _root_id(record: dict) -> str | None:
    p = record.get('payload')
    if record.get('type') != 'session_meta' or not isinstance(p, dict):
        return None
    source = p.get('source')
    if (p.get('parent_thread_id') or p.get('thread_source') not in ('user', 'voice_chat')
            or isinstance(source, dict) and ('subagent' in source or 'guardian' in source)):
        return None
    value = p.get('id')
    return value if isinstance(value, str) and value else None


class _Rollout:
    """Track one rollout by byte offset, opening it only while reading.

    Holding the handle open for the process lifetime blocks deletion on
    Windows, where Codex removes old rollouts while the bridge is running.
    """

    def __init__(self, path: Path):
        self.path = path
        stat = path.stat()
        self.inode = stat.st_ino
        self.mtime_ns = stat.st_mtime_ns
        self.buffer = b''
        self.skip_long = False
        self.turn = None
        with path.open('rb') as file:
            first = file.readline(_MAX_LINE + 1)
            if not first.endswith(b'\n'):
                raise ValueError('Incomplete session metadata')
            self.offset = file.tell()
        try:
            meta = json.loads(first)
            self.session = _root_id(meta) if isinstance(meta, dict) else None
        except (ValueError, UnicodeDecodeError):
            self.session = None

    def close(self):
        """Nothing stays open between polls; kept for the adapter's cleanup."""

    def replaced(self, stat) -> bool:
        same_inode = bool(stat.st_ino) and bool(self.inode) and stat.st_ino == self.inode
        if self.inode and stat.st_ino and not same_inode:
            return True
        return (stat.st_size < self.offset
                or (stat.st_size == self.offset and stat.st_mtime_ns != self.mtime_ns))

    def read(self, stat):
        """Yield only fresh relevant records, retaining incomplete trailing lines."""
        self.mtime_ns = stat.st_mtime_ns
        with self.path.open('rb') as file:
            file.seek(self.offset)
            while True:
                chunk = file.read(65536)
                if not chunk:
                    return
                self.offset += len(chunk)
                parts = (self.buffer + chunk).split(b'\n')
                self.buffer = parts.pop()
                for line in parts:
                    if self.skip_long:
                        self.skip_long = False
                        continue
                    if len(line) > _MAX_LINE or not any(m in line for m in _MARKERS):
                        continue
                    try:
                        record = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if not isinstance(record, dict):
                        continue
                    p = record.get('payload')
                    if not isinstance(p, dict):
                        continue
                    if record.get('type') == 'event_msg' and p.get('type') == 'task_started':
                        turn = p.get('turn_id')
                        self.turn = turn if isinstance(turn, str) else None
                        continue
                    meta = p.get('internal_chat_message_metadata_passthrough')
                    turn = meta.get('turn_id') if isinstance(meta, dict) else None
                    yield record, turn if isinstance(turn, str) else self.turn
                if len(self.buffer) > _MAX_LINE:
                    self.buffer = b''
                    self.skip_long = True


@dataclass(frozen=True)
class _Pending:
    timestamp: float
    path: Path
    turn: str | None


class AttentionAdapter:
    def __init__(self, root: Path, stale_seconds: float = 600, *,
                 state_path: Path | None = None, start_timestamp: float | None = None,
                 initial_pending=None):
        """Track cards from an explicit starting boundary, without age expiry.

        ``stale_seconds`` is accepted only for compatibility with the old bridge;
        it never expires cards. Without a cache or ``start_timestamp``, the first
        poll's time becomes the installation boundary. ``initial_pending`` may
        seed confirmed old-adapter cards as metadata dicts containing session_id,
        call_id, index, timestamp, optional turn. It is used only without a cache.
        A corrupt/incompatible existing cache raises ValueError instead of being
        silently overwritten and losing pending cards.
        """
        if stale_seconds <= 0:
            raise ValueError('stale_seconds must be positive')
        if start_timestamp is not None and not _valid_time(start_timestamp):
            raise ValueError('start_timestamp must be a finite nonnegative time')
        self.root = Path(root)
        self.stale_seconds = stale_seconds
        self.state_path = Path(state_path) if state_path is not None else None
        self.start_timestamp = start_timestamp
        self.files: dict[Path, _Rollout] = {}
        self.ignored = {}
        self.pending: dict[tuple[str, str, int], _Pending] = {}
        # Tombstones prevent a duplicate/rotated older rollout from reviving replies.
        self.resolved: dict[tuple[str, str, int], float] = {}
        self.aborted: dict[tuple[str, str | None], float] = {}
        self.closed_sessions: dict[str, float] = {}
        self._dirty = False
        self._last_state = (False, 0)
        if self.state_path is not None and self.state_path.exists():
            self._load_state()
        elif initial_pending is not None:
            for item in initial_pending:
                self._seed(item)

    def _seed(self, item):
        if not isinstance(item, dict):
            raise ValueError('Pending seed must contain metadata dictionaries')
        session = item.get('session_id')
        identity = _question_id([item.get('call_id'), item.get('index')])
        stamp = item.get('timestamp')
        turn = item.get('turn')
        if (not isinstance(session, str) or not session or identity is None
                or not _valid_time(stamp) or turn is not None and not isinstance(turn, str)):
            raise ValueError('Invalid pending seed metadata')
        self.pending[(session, *identity)] = _Pending(stamp, self.root, turn)
        self._dirty = True

    def pending_metadata(self) -> list[dict]:
        """Export only identities, timestamps and turn IDs for safe migration."""
        return [dict(session_id=s, call_id=c, index=i, timestamp=p.timestamp, turn=p.turn)
                for (s, c, i), p in sorted(self.pending.items())]

    def _load_state(self):
        try:
            if self.state_path.stat().st_size > 16_000_000:
                raise ValueError('Oversized cache')
            data = json.loads(self.state_path.read_text(encoding='utf-8'))
            if (not isinstance(data, dict) or data.get('version') != _CACHE_VERSION
                    or data.get('root') != str(self.root.resolve())
                    or not _valid_time(data.get('start_timestamp'))):
                raise ValueError('Incompatible cache')
            self.start_timestamp = data['start_timestamp']
            if not all(isinstance(data.get(k), list)
                       for k in ('pending', 'resolved', 'aborted', 'closed_sessions')):
                raise ValueError('Invalid cache collections')
            for item in data['pending']:
                self._seed(item)
            for item in data['resolved']:
                s, c, i, stamp = item
                identity = _question_id([c, i])
                if not isinstance(s, str) or not s or identity is None or not _valid_time(stamp):
                    raise ValueError('Invalid resolution')
                self.resolved[(s, *identity)] = stamp
            for s, turn, stamp in data['aborted']:
                if (not isinstance(s, str) or not s or not _valid_time(stamp)
                        or turn is not None and not isinstance(turn, str)):
                    raise ValueError('Invalid cancellation')
                self.aborted[(s, turn)] = stamp
            for s, stamp in data['closed_sessions']:
                if not isinstance(s, str) or not s or not _valid_time(stamp):
                    raise ValueError('Invalid chat closure')
                self.closed_sessions[s] = stamp
            self.pending = {k: p for k, p in self.pending.items()
                            if k not in self.resolved
                            and self.closed_sessions.get(k[0], -1) < p.timestamp
                            and self.aborted.get((k[0], None), -1) < p.timestamp
                            and (p.turn is None or self.aborted.get((k[0], p.turn), -1) < p.timestamp)}
            self._dirty = False
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ValueError('Attention state cache is unreadable or invalid; preserve it for recovery') from exc

    def _save_state(self):
        if not self._dirty or self.state_path is None or self.start_timestamp is None:
            return
        data = {'version': _CACHE_VERSION, 'root': str(self.root.resolve()),
                'start_timestamp': self.start_timestamp, 'pending': self.pending_metadata(),
                'resolved': [[*k, v] for k, v in sorted(self.resolved.items())],
                'aborted': [[*k, v] for k, v in self.aborted.items()],
                'closed_sessions': [[k, v] for k, v in sorted(self.closed_sessions.items())]}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=self.state_path.name + '.', suffix='.tmp',
                                   dir=self.state_path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(data, stream, ensure_ascii=True, separators=(',', ':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.state_path)
            self._dirty = False
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def cancel_question(self, session: str, question_id, now: float | None = None) -> bool:
        """Resolve an exact card ID after an explicit UI cancellation/answer."""
        identity = _question_id(question_id)
        stamp = time.time() if now is None else now
        if not isinstance(session, str) or not session or identity is None or not _valid_time(stamp):
            raise ValueError('Cancellation requires an exact chat/card identity and valid time')
        key = (session, *identity)
        changed = key in self.pending
        self.pending.pop(key, None)
        self._dirty = self._dirty or changed
        if stamp > self.resolved.get(key, -1):
            self.resolved[key] = stamp
            self._dirty = True
        self._save_state()
        return changed

    def close_chat(self, session: str, now: float | None = None) -> bool:
        """Clear a chat only on an authoritative archive/delete/close event.

        An idle chat, completed turn, closed UI window, or lost socket is NOT a
        closed task. Reopening the chat may introduce new card IDs normally.
        """
        stamp = time.time() if now is None else now
        if not isinstance(session, str) or not session or not _valid_time(stamp):
            raise ValueError('Chat closure requires an exact chat identity and valid time')
        keys = [k for k in self.pending if k[0] == session]
        for key in keys:
            self.resolved[key] = max(stamp, self.resolved.get(key, -1))
            del self.pending[key]
        self.closed_sessions[session] = max(stamp, self.closed_sessions.get(session, -1))
        self._dirty = True
        self._save_state()
        return bool(keys)

    def reconcile_open_questions(self, session: str, question_ids, *,
                                 authoritative: bool = False, now: float | None = None) -> bool:
        """Drop missing tracked IDs only from a complete authoritative per-chat list.

        No card is imported from an old UI snapshot. Transport errors, incomplete
        lists and idle-status observations must not pass authoritative=True.
        Malformed IDs reject the whole snapshot instead of clearing valid cards.
        """
        if not authoritative:
            return False
        if not isinstance(session, str) or not session or not isinstance(question_ids, (list, tuple, set)):
            raise ValueError('Reconciliation requires a complete per-chat ID list')
        identities = {_question_id(value) for value in question_ids}
        if None in identities:
            raise ValueError('Malformed card ID in authoritative snapshot')
        changed = False
        for key in list(self.pending):
            if key[0] == session and key[1:] not in identities:
                changed = self.cancel_question(session, key[1:], now) or changed
        return changed

    def _drop_file(self, path):
        file = self.files.pop(path, None)
        if file:
            file.close()
        # A file can rotate or be temporarily unavailable while its UI card lives.

    def _consume(self, session, path, record, turn, now):
        stamp = _timestamp(record)
        if stamp is None or stamp > now:
            return
        p = record['payload']
        if record.get('type') == 'event_msg' and p.get('type') == 'turn_aborted':
            abort_turn = p.get('turn_id')
            abort_turn = abort_turn if isinstance(abort_turn, str) else None
            key = (session, abort_turn)
            self.aborted[key] = max(stamp, self.aborted.get(key, 0))
            self.pending = {k:v for k,v in self.pending.items()
                            if not (k[0] == session and v.timestamp <= stamp
                                    and (abort_turn is None or v.turn == abort_turn))}
            self._dirty = True
            return
        if record.get('type') != 'response_item':
            return
        if p.get('type') == 'function_call' and p.get('name') in (_TOOL, 'functions.'+_TOOL):
            if stamp < self.start_timestamp or stamp <= self.closed_sessions.get(session, -1):
                return
            call = p.get('call_id')
            if not isinstance(call, str) or not call:
                return
            try:
                args = json.loads(p.get('arguments', ''))
            except (ValueError, TypeError):
                return
            if not isinstance(args, dict) or not isinstance(args.get('questions'), list):
                return
            for index, question in enumerate(args['questions']):
                if not isinstance(question, dict) or not isinstance(question.get('title'), str) or not question['title'].strip():
                    continue
                key = (session, call, index)
                if (key in self.resolved
                        or self.aborted.get((session, None), 0) >= stamp
                        or turn is not None and self.aborted.get((session, turn), 0) >= stamp):
                    continue
                old = self.pending.get(key)
                if old is None or stamp > old.timestamp:
                    self.pending[key] = _Pending(stamp, path, turn)
                    self._dirty = True
        elif p.get('type') == 'function_call_output':
            call = p.get('call_id')
            # A successfully scheduled async card returns {accepted: true}; it
            # remains pending. Explicit rejection means no card was presented.
            try:
                result = json.loads(p.get('output', ''))
            except (ValueError, TypeError):
                return
            if isinstance(result, dict) and result.get('accepted') is False:
                for key in list(self.pending):
                    if key[:2] == (session, call):
                        self.resolved[key] = stamp
                        del self.pending[key]
                        self._dirty = True
        elif p.get('type') == 'message' and p.get('role') == 'user':
            if _direct_user_reply(p):
                for key, pending in list(self.pending.items()):
                    if key[0] == session and pending.timestamp <= stamp:
                        self.resolved[key] = max(stamp, self.resolved.get(key, 0))
                        del self.pending[key]
                        self._dirty = True
                return
            content = p.get('content')
            if not isinstance(content, list):
                return
            for part in content:
                if not isinstance(part, dict) or not isinstance(part.get('text'), str):
                    continue
                text = part['text'].strip()
                if not text.startswith(_START) or not text.endswith(_END):
                    continue
                try:
                    answers = json.loads(text[len(_START):-len(_END)].strip())
                except ValueError:
                    continue
                if not isinstance(answers, list):
                    continue
                for answer in answers:
                    if not isinstance(answer, dict) or 'answer' not in answer:
                        continue
                    try:
                        key = json.loads(answer.get('questionItemId', ''))
                    except (ValueError, TypeError):
                        continue
                    if not (isinstance(key, list) and len(key) == 3 and key[0] == _TOOL
                            and isinstance(key[1], str) and type(key[2]) is int and key[2] >= 0):
                        continue
                    identity = (session, key[1], key[2])
                    self.resolved[identity] = max(stamp, self.resolved.get(identity, 0))
                    self._dirty = True
                    pending = self.pending.get(identity)
                    if pending and pending.timestamp <= stamp:
                        del self.pending[identity]

    def poll(self, now: float | None = None) -> bool:
        live_clock = now is None
        now = time.time() if now is None else now
        if not _valid_time(now):
            raise ValueError('poll time must be finite and nonnegative')
        if self.start_timestamp is None:
            self.start_timestamp = now
            self._dirty = True
        # Seeded pending cards may predate the first-install boundary. Read their
        # later replies/cancellations too, but never import unseeded older asks.
        replay_since = min([self.start_timestamp] + [p.timestamp for p in self.pending.values()])
        candidates = {}
        if self.root.exists():
            for path in self.root.rglob('rollout-*.jsonl'):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_mtime >= replay_since or path in self.files:
                    candidates[path] = stat
        for path in list(self.files):
            if path not in candidates or self.files[path].replaced(candidates[path]):
                self._drop_file(path)
        self.ignored = {p:s for p,s in self.ignored.items() if p in candidates}
        events = []
        for path, stat in candidates.items():
            signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            if self.ignored.get(path) == signature:
                continue
            if path not in self.files:
                try:
                    file = _Rollout(path)
                except (OSError, ValueError):
                    continue
                if not file.session:
                    file.close()
                    self.ignored[path] = signature
                    continue
                self.files[path] = file
            file = self.files[path]
            try:
                for record, turn in file.read(stat):
                    stamp = _timestamp(record)
                    if stamp is not None and stamp >= replay_since:
                        events.append((stamp, file.session, path, record, turn))
            except OSError:
                self._drop_file(path)
        # Stable timestamp ordering allows question/reply records in different
        # rollout instances of one chat to resolve consistently on startup.
        events.sort(key=lambda e:e[0])
        # A writer may append during this scan. Compare to the end of the scan
        # so a valid fresh record is not discarded as a few milliseconds future.
        if live_clock:
            now = time.time()
        for _, session, path, record, turn in events:
            self._consume(session, path, record, turn, now)
        self._save_state()
        current = self.selected(now)
        changed = current != self._last_state
        self._last_state = current
        return changed

    def selected(self, now: float | None = None) -> tuple[bool, int]:
        # now is retained as a clock-injectable API compatibility argument. It
        # intentionally cannot expire an unanswered card, even after long sleep.
        return bool(self.pending), len(self.pending)

    def close(self):
        self._save_state()
        for file in self.files.values():
            file.close()
        self.files.clear()
        self.pending.clear()
        self.resolved.clear()
        self.aborted.clear()
        self.closed_sessions.clear()
        self.ignored.clear()
        self._last_state = (False, 0)
