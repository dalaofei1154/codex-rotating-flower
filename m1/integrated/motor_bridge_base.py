#!/usr/bin/env python3
"""Drive connected ESP32 motors from local Codex and/or WorkBuddy tasks.

This adapter reads Codex's local rollout files. Their format is internal and may
change; the rest of the bridge only sees (session id, active, effort) states.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import glob
import json
import os
import select
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


EFFORT_SPEED = {
    "none": "LOW", "minimal": "LOW", "low": "LOW",
    "medium": "MEDIUM", "high": "HIGH", "xhigh": "XHIGH",
    "max": "ULTRA", "ultra": "ULTRA",
}
SPEED_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "XHIGH": 4, "ULTRA": 5}
INTERESTING_EVENTS = (
    b"thread_settings_applied", b"task_started", b"task_complete",
    b"turn_aborted", b"turn_context"
)


def event_time(record: dict) -> float:
    value = record.get("timestamp")
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return 0.0


@dataclass
class TaskState:
    session_id: str
    effort: str | None = None
    active: bool = False
    turn_id: str | None = None
    started_at: float = 0.0
    pending_context: tuple[str, str] | None = None

    @property
    def speed(self) -> str | None:
        if not self.active:
            return None
        return EFFORT_SPEED.get(self.effort or "", "MEDIUM")

    def consume(self, record: dict) -> bool:
        if record.get("type") == "turn_context":
            context = record.get("payload") or {}
            turn_id = context.get("turn_id")
            effort = context.get("effort")
            if isinstance(turn_id, str) and isinstance(effort, str):
                self.pending_context = (turn_id, effort.lower())
                if self.active and self.turn_id == turn_id:
                    changed = self.effort != effort.lower()
                    self.effort = effort.lower()
                    return changed
            return False
        if record.get("type") != "event_msg":
            return False
        event = record.get("payload") or {}
        kind = event.get("type")
        before = (self.effort, self.active, self.turn_id)
        if kind == "thread_settings_applied":
            settings = event.get("thread_settings") or {}
            value = settings.get("reasoning_effort")
            if isinstance(value, str):
                self.effort = value.lower()
        elif kind == "task_started":
            self.active = True
            self.turn_id = event.get("turn_id")
            self.started_at = event_time(record)
            if self.pending_context and self.pending_context[0] == self.turn_id:
                self.effort = self.pending_context[1]
        elif kind in ("task_complete", "turn_aborted"):
            if self.active and (not event.get("turn_id") or event.get("turn_id") == self.turn_id):
                self.active = False
        return before != (self.effort, self.active, self.turn_id)


def is_root_meta(record: dict) -> bool:
    if record.get("type") != "session_meta":
        return False
    meta = record.get("payload") or {}
    source = meta.get("source")
    return (not meta.get("parent_thread_id")
            and meta.get("thread_source") in ("user", "voice_chat")
            and not (isinstance(source, dict) and ("subagent" in source or "guardian" in source))
            and isinstance(meta.get("id"), str))


class RolloutFile:
    def __init__(self, path: Path):
        self.path = path
        self.file = path.open("rb")
        first = self.file.readline()
        try:
            meta = json.loads(first)
        except (UnicodeDecodeError, json.JSONDecodeError):
            meta = {}
        self.is_root = is_root_meta(meta)
        self.state = TaskState((meta.get("payload") or {}).get("id", ""))
        self.pending = b""
        self.skip_long_line = False
        self.size = self.file.tell()
        stat = path.stat()
        self.mtime = stat.st_mtime
        self.inode = stat.st_ino
        if self.is_root:
            self.poll()

    def close(self) -> None:
        self.file.close()

    def poll(self) -> bool:
        # Let the adapter remove this task immediately if its rollout vanishes.
        # Keeping its old active state would continue refreshing the motor watchdog.
        stat = self.path.stat()
        if stat.st_ino != self.inode or stat.st_size < self.size:
            self.file.close()
            self.file = self.path.open("rb")
            self.inode = stat.st_ino
            self.file.seek(0)
            self.pending = b""
            self.skip_long_line = False
            self.size = 0
            self.state = TaskState(self.state.session_id)
        self.mtime = stat.st_mtime
        changed = False
        while True:
            chunk = self.file.read(65536)
            if not chunk:
                break
            self.size += len(chunk)
            data = self.pending + chunk
            parts = data.split(b"\n")
            self.pending = parts.pop()
            for line in parts:
                if self.skip_long_line:
                    self.skip_long_line = False
                    continue
                if not any(marker in line for marker in INTERESTING_EVENTS):
                    continue
                try:
                    changed = self.state.consume(json.loads(line)) or changed
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            if len(self.pending) > 8_000_000:
                self.pending = b""
                self.skip_long_line = True
        return changed


class CodexRolloutAdapter:
    def __init__(self, root: Path, stale_seconds: float = 600):
        self.root = root
        self.stale_seconds = stale_seconds
        self.files: dict[Path, RolloutFile] = {}

    def poll(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        changed = False
        if self.root.exists():
            for path in self.root.rglob("rollout-*.jsonl"):
                try:
                    recent = now - path.stat().st_mtime <= self.stale_seconds
                except OSError:
                    continue
                if recent and path not in self.files:
                    try:
                        entry = RolloutFile(path)
                    except OSError:
                        continue
                    if entry.is_root:
                        self.files[path] = entry
                        changed = True
                    else:
                        entry.close()
        for path, entry in list(self.files.items()):
            try:
                changed = entry.poll() or changed
            except OSError:
                entry.close()
                del self.files[path]
                changed = True
                continue
            if now - entry.mtime > self.stale_seconds:
                entry.close()
                del self.files[path]
                changed = True
        return changed

    def selected(self, now: float | None = None) -> tuple[str, str | None, int]:
        now = time.time() if now is None else now
        active = [entry.state for entry in self.files.values()
                  if entry.state.speed is not None and now - entry.mtime <= self.stale_seconds]
        if not active:
            return "STOP", None, 0
        selected = max(active, key=lambda s: (SPEED_RANK[s.speed], s.started_at))
        return "RUN " + selected.speed, selected.session_id, len(active)

    def close(self) -> None:
        for entry in self.files.values():
            entry.close()
        self.files.clear()


def default_workbuddy_root() -> Path:
    roots = [Path.home() / ".workbuddy", Path.home() / ".workbuddy-ai"]
    return next((root for root in roots if (root / "workbuddy.db").is_file()), roots[0])


def workbuddy_model_speed(model: object) -> tuple[str, str]:
    """Map selected product tiers, not model brands or measured cloud compute."""
    if not isinstance(model, str) or not model.strip():
        return "LOW", "missing model (legacy)"
    tiers = {
        "fast-model": ("LOW", "product fast"),
        "balanced-model": ("HIGH", "product balanced"),
        "deep-model": ("ULTRA", "product deep"),
    }
    return tiers.get(model.strip(), ("HIGH", "independent/unknown model (neutral)"))


class WorkBuddyDatabaseAdapter:
    """Read task/process metadata only; never change WorkBuddy's database.

    This is an internal WorkBuddy format, inspected in macOS 5.8.3/5.9.3. A running
    task must also have a live, matching CLI worker registration. This prevents
    an old 'working' database row from running the motor after a worker exits.

    sessions.model is a selected configuration, not an actual inference metric.
    Latch it while a worker's turn is active (including permission/question waits)
    so a selection for the next prompt does not change the current turn's speed.
    Attaching mid-turn or recovering lost metadata can only infer the tier from
    the currently selected model. A completed/restarted turn entirely between
    polls on the same worker may retain the previous tier: the DB has no turn ID.
    """

    def __init__(self, root: Path, stale_seconds: float = 600):
        self.root = root
        self.stale_seconds = stale_seconds
        self.active: dict[str, float] = {}
        self.active_speeds: dict[str, str] = {}
        self.mapping_counts: dict[str, int] = {}
        self._latched: dict[str, tuple[frozenset[int], str, str]] = {}
        self.status_counts: dict[str, int] = {}
        self.live_workers = 0
        self.last_error: str | None = None

    def _live_sessions(self) -> dict[str, frozenset[int]]:
        sessions: dict[str, set[int]] = {}
        for path in (self.root / "sessions").glob("*.json"):
            if not path.stem.isdecimal():
                continue
            try:
                if path.stat().st_size > 65536:
                    continue
                record = json.loads(path.read_text())
                if not isinstance(record, dict) or record.get("kind") == "prewarm":
                    continue
                pid = record.get("pid")
                session_id = record.get("sessionId")
                if (type(pid) is not int or pid <= 0 or str(pid) != path.stem
                        or not isinstance(session_id, str) or not session_id):
                    continue
                try:
                    os.kill(pid, 0)
                except PermissionError:
                    # A sandbox may deny the probe even when the worker exists.
                    continue
                sessions.setdefault(session_id, set()).add(pid)
            except (OSError, ValueError):
                continue
        return {session_id: frozenset(pids) for session_id, pids in sessions.items()}

    def poll(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        before = (self.active, self.active_speeds, self.mapping_counts,
                  self.status_counts, self.live_workers, self.last_error)
        self.active = {}
        self.active_speeds = {}
        self.mapping_counts = {}
        next_latched = {}
        self.status_counts = {}
        self.live_workers = 0
        self.last_error = None
        database = self.root / "workbuddy.db"
        if not database.is_file():
            self.last_error = "WorkBuddy database not found; open WorkBuddy and start a local task"
        else:
            connection = None
            try:
                connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True,
                                             timeout=0.2)
                connection.execute("PRAGMA query_only = ON")
                columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
                model_column = "model" if "model" in columns else "NULL"
                rows = connection.execute(f"""
                    SELECT id, status, updated_at, {model_column} FROM sessions
                    WHERE transport = 'local' AND deleted_at IS NULL
                """).fetchall()
                live = self._live_sessions()
                self.live_workers = len(live)
                for session_id, status, updated_at, model in rows:
                    status = str(status).lower()
                    self.status_counts[status] = self.status_counts.get(status, 0) + 1
                    if (status not in ("working", "planning", "pending", "waiting_permission")
                            or session_id not in live):
                        continue
                    if not isinstance(updated_at, (int, float)):
                        continue
                    # WorkBuddy stores epoch milliseconds. Unknown/future values
                    # fail closed rather than keeping a motor running forever.
                    updated_seconds = updated_at / 1000
                    if not 0 <= now - updated_seconds <= self.stale_seconds:
                        continue
                    workers = live[session_id]
                    latched = self._latched.get(session_id)
                    if latched is not None and latched[0] != workers:
                        latched = None
                    if status in ("pending", "waiting_permission"):
                        if latched is not None:
                            next_latched[session_id] = latched
                        continue
                    if latched is None:
                        speed, basis = workbuddy_model_speed(model)
                        latched = (workers, speed, basis)
                    next_latched[session_id] = latched
                    _, speed, basis = latched
                    self.active[session_id] = updated_seconds
                    self.active_speeds[session_id] = speed
                    mapping = f"{basis} -> {speed}"
                    self.mapping_counts[mapping] = self.mapping_counts.get(mapping, 0) + 1
            except (OSError, sqlite3.Error):
                self.active = {}
                self.active_speeds = {}
                self.mapping_counts = {}
                next_latched = {}
                self.last_error = "WorkBuddy metadata unavailable or schema changed; motor contribution is STOP"
            finally:
                if connection is not None:
                    connection.close()
        self._latched = next_latched
        return before != (self.active, self.active_speeds, self.mapping_counts,
                          self.status_counts, self.live_workers, self.last_error)

    def selected(self, now: float | None = None) -> tuple[str, str | None, int]:
        now = time.time() if now is None else now
        active = {key: updated for key, updated in self.active.items()
                  if 0 <= now - updated <= self.stale_seconds}
        if not active:
            return "STOP", None, 0
        session_id = max(active, key=lambda key: (SPEED_RANK[self.active_speeds[key]], active[key]))
        return "RUN " + self.active_speeds[session_id], session_id, len(active)

    def close(self) -> None:
        self.active.clear()
        self.active_speeds.clear()
        self.mapping_counts.clear()
        self._latched.clear()


class CombinedAdapter:
    def __init__(self, adapters: dict):
        self.adapters = adapters

    def poll(self, now: float | None = None) -> bool:
        changed = False
        for adapter in self.adapters.values():
            changed = adapter.poll(now) or changed
        return changed

    def selected(self, now: float | None = None) -> tuple[str, str | None, int]:
        states = [adapter.selected(now) for adapter in self.adapters.values()]
        count = sum(state[2] for state in states)
        running = [state for state in states if state[0] != "STOP"]
        if not running:
            return "STOP", None, 0
        command, session_id, _ = max(running, key=lambda state: SPEED_RANK[state[0][4:]])
        return command, session_id, count

    def close(self) -> None:
        for adapter in self.adapters.values():
            adapter.close()


def serial_candidates() -> list[str]:
    patterns = ["/dev/cu.usbmodem*", "/dev/cu.usbserial*",
                "/dev/serial/by-id/*", "/dev/ttyACM*", "/dev/ttyUSB*"]
    return sorted({path for pattern in patterns for path in glob.glob(pattern)})


class MotorSerial:
    def __init__(self, requested_port: str = "auto"):
        self.requested_port = requested_port
        self.fd: int | None = None
        self.path: str | None = None
        self.last_command: str | None = None
        self.last_sent_at = 0.0
        self.last_probe_at = -float("inf")

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
        self.fd = None
        self.path = None
        self.last_command = None

    def _probe(self, path: str) -> bool:
        fd = None
        try:
            stty_flag = "-f" if sys.platform == "darwin" else "-F"
            subprocess.run(["stty", stty_flag, path, "115200", "raw", "-echo"],
                           check=True, capture_output=True, timeout=2)
            fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            time.sleep(0.6)
            os.write(fd, b"PING\n")
            deadline = time.monotonic() + 1.5
            reply = b""
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], 0.2)
                if ready:
                    reply += os.read(fd, 4096)
                    if b"PONG" in reply:
                        self.fd = fd
                        self.path = path
                        self.last_command = None
                        print(f"Motor connected: {path}", flush=True)
                        return True
        except (OSError, subprocess.SubprocessError):
            pass
        if fd is not None:
            os.close(fd)
        return False

    def connect(self) -> bool:
        if self.fd is not None and self.path and os.path.exists(self.path):
            return True
        if self.fd is not None:
            self.close()
        now = time.monotonic()
        if now - self.last_probe_at < 2:
            return False
        self.last_probe_at = now
        paths = ([self.requested_port] if self.requested_port != "auto"
                 else serial_candidates())
        for path in paths:
            if self._probe(path):
                return True
        return False

    def send(self, command: str) -> bool:
        if not self.connect():
            return False
        now = time.monotonic()
        if command == self.last_command and now - self.last_sent_at < 2:
            return True
        try:
            os.write(self.fd, (command + "\n").encode("ascii"))
            if command != self.last_command:
                print(f"Motor [{self.path}]: {command}", flush=True)
            self.last_command = command
            self.last_sent_at = now
            ready, _, _ = select.select([self.fd], [], [], 0)
            if ready:
                os.read(self.fd, 4096)
            return True
        except OSError:
            print(f"Motor disconnected: {self.path}; scanning USB ports", flush=True)
            self.close()
            return False


class MotorGroup:
    """Broadcast one task state, including to flowers plugged in while running."""

    def __init__(self, requested_port: str = "auto"):
        self.requested_port = requested_port
        self.motors: dict[str, MotorSerial] = {}

    def send(self, command: str) -> bool:
        paths = (serial_candidates() if self.requested_port == "auto"
                 else [self.requested_port])
        for path in list(self.motors):
            if path not in paths:
                print(f"Motor disconnected: {path}", flush=True)
                self.motors.pop(path).close()
        for path in paths:
            if path not in self.motors:
                self.motors[path] = MotorSerial(path)

        # Refresh every connected motor before probing. Limit probing to one
        # port per cycle so an unresponsive device cannot starve heartbeats.
        sent = False
        for motor in self.motors.values():
            if motor.fd is not None:
                sent = motor.send(command) or sent
        now = time.monotonic()
        pending = [motor for motor in self.motors.values()
                   if motor.fd is None and now - motor.last_probe_at >= 2]
        if pending:
            motor = min(pending, key=lambda item: item.last_probe_at)
            sent = motor.send(command) or sent
        return sent

    def close(self) -> None:
        for motor in self.motors.values():
            if motor.fd is not None:
                motor.send("STOP")
            motor.close()
        self.motors.clear()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"
    parser.add_argument("--sessions-root", type=Path, default=default_root)
    parser.add_argument("--source", choices=("codex", "workbuddy", "both"), default="codex")
    parser.add_argument("--workbuddy-root", type=Path, default=default_workbuddy_root())
    parser.add_argument("--port", default="auto",
                        help="Serial device, or auto for all responding flowers (default)")
    parser.add_argument("--stale-seconds", type=float, default=600)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true", help="Show aggregate state without opening USB")
    parser.add_argument("--no-motor", action="store_true", help="Watch task state without opening USB")
    args = parser.parse_args(argv)
    if args.stale_seconds <= 0:
        parser.error("--stale-seconds must be positive")
    lock_file = None
    if not args.once and not args.no_motor:
        lock_path = Path(tempfile.gettempdir()) / f"codex-motor-bridge-{os.getuid()}.lock"
        lock_file = lock_path.open("a+")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another global motor bridge is already running", file=sys.stderr)
            lock_file.close()
            return 2
    adapters = {}
    if args.source in ("codex", "both"):
        adapters["Codex"] = CodexRolloutAdapter(args.sessions_root, args.stale_seconds)
    if args.source in ("workbuddy", "both"):
        adapters["WorkBuddy"] = WorkBuddyDatabaseAdapter(args.workbuddy_root, args.stale_seconds)
    adapter = CombinedAdapter(adapters)
    motors = MotorGroup(args.port)
    previous_handler = signal.getsignal(signal.SIGTERM)

    def stop_on_signal(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_on_signal)
    try:
        adapter.poll()
        previous = None
        while True:
            command, _, count = adapter.selected()
            details = []
            for name, source in adapters.items():
                details.append(f"{name} active: {source.selected()[2]}")
                if isinstance(source, WorkBuddyDatabaseAdapter):
                    details.append(f"WorkBuddy statuses: {source.status_counts}; live workers: {source.live_workers}")
                    details.append(f"WorkBuddy selected-tier mapping: {source.mapping_counts}")
                    if source.last_error:
                        details.append(source.last_error)
            state = (command, count, tuple(details))
            if state != previous:
                print("; ".join(details) + f"; motor: {command}", flush=True)
                previous = state
            if args.once:
                return 0
            if not args.no_motor:
                motors.send(command)
            time.sleep(max(0.1, args.poll_seconds))
            adapter.poll()
    except KeyboardInterrupt:
        print("Bridge stopped", flush=True)
        return 0
    finally:
        motors.close()
        adapter.close()
        signal.signal(signal.SIGTERM, previous_handler)
        if lock_file is not None:
            lock_file.close()


if __name__ == "__main__":
    sys.exit(main())
