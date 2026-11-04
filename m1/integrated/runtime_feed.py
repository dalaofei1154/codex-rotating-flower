"""Read-only observer of the existing local Codex desktop IPC stream.

This private desktop protocol was verified against installed 26.1027.51404.
It never starts/resumes a chat or sends approval/input decisions. No message
text or tool arguments are exposed in snapshot() or written to disk.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import struct
import threading
import time
import uuid


WATCH_FIELDS = {"id", "hostId", "parentThreadId", "threadSource", "source",
                "threadRuntimeStatus", "requests", "latestReasoningEffort"}
VALID_STATUS = {"active", "idle", "notLoaded", "systemError"}
VALID_FLAGS = {"waitingOnApproval", "waitingOnUserInput"}


def apply_metadata_patches(state, patches):
    """Apply only watched Immer paths; caller requests a fresh snapshot on error."""
    out = copy.deepcopy(state)
    for patch in patches:
        path = patch.get("path", [])
        op = patch.get("op")
        if not path:
            if op == "replace" and isinstance(patch.get("value"), dict):
                out = {k: copy.deepcopy(v) for k, v in patch["value"].items() if k in WATCH_FIELDS}
            continue
        if path[0] not in WATCH_FIELDS:
            continue
        cursor = out
        for key in path[:-1]:
            if isinstance(cursor, list) and (type(key) is not int or key < 0 or key >= len(cursor)):
                raise ValueError("invalid metadata index")
            cursor = cursor[key]
        key = path[-1]
        if isinstance(cursor, list):
            limit = len(cursor) if op == "add" else len(cursor) - 1
            if not (op == "add" and key == "-") and (type(key) is not int or key < 0 or key > limit):
                raise ValueError("invalid metadata index")
        if op == "remove":
            if isinstance(cursor, list):
                cursor.pop(int(key))
            else:
                cursor.pop(key, None)
        elif op in ("add", "replace"):
            value = copy.deepcopy(patch.get("value"))
            if isinstance(cursor, list):
                if op == "add":
                    cursor.insert(len(cursor) if key == "-" else int(key), value)
                else:
                    cursor[int(key)] = value
            else:
                cursor[key] = value
        else:
            raise ValueError("unsupported metadata patch")
    return out


def normalize_metadata(thread_id, state, observed_at):
    status = state.get("threadRuntimeStatus")
    normalized_status = None
    if isinstance(status, dict) and status.get("type") in VALID_STATUS:
        normalized_status = {"type": status["type"]}
        if status["type"] == "active":
            flags = status.get("activeFlags")
            if not isinstance(flags, list) or any(not isinstance(f, str) or f not in VALID_FLAGS for f in flags):
                normalized_status = None
            else:
                normalized_status["activeFlags"] = list(flags)
    requests = []
    if not isinstance(state.get("requests", []), list):
        raise ValueError("invalid requests metadata")
    for request in state.get("requests", []):
        if not isinstance(request, dict):
            continue
        # Explicit allowlist: no command, input, prompt, question, or output text.
        record = {k: request[k] for k in ("id", "requestId", "type", "method", "turnId", "itemId")
                  if k in request and isinstance(request[k], (str, int))}
        params = request.get("params")
        if isinstance(params, dict):
            for k in ("threadId", "turnId", "itemId"):
                if isinstance(params.get(k), (str, int)):
                    record[k] = params[k]
        requests.append(record)
    parent = state.get("parentThreadId")
    return {"thread_id": thread_id, "host_id": state.get("hostId", "local"),
            "parent_thread_id": parent, "runtime_status": normalized_status,
            "requests": requests, "observed_at": observed_at,
            "owner_found": True, "archived": False,
            "latest_reasoning_effort": state.get("latestReasoningEffort")}


class DesktopRuntimeFeed:
    """Background socket reader; set_targets()/snapshot() never perform I/O."""

    def __init__(self, socket_path=None, refresh_seconds=2.0, reconnect_seconds=2.0):
        self.socket_path = str(socket_path or Path.home() / ".codex/ipc/ipc.sock")
        self.refresh_seconds = max(2.0, float(refresh_seconds))
        self.reconnect_seconds = max(0.2, float(reconnect_seconds))
        self._lock = threading.Lock()
        self._targets = set()
        self._threads = {}
        self._stop = threading.Event()
        self._connected = False
        self._error = "not_started"
        self._last_message_at = None
        self._sock = None
        self._worker = threading.Thread(target=self._run, name="flower-desktop-observer", daemon=True)
        self._worker.start()

    def set_targets(self, thread_ids):
        valid = set()
        for value in thread_ids:
            try:
                valid.add(str(uuid.UUID(str(value))))
            except (ValueError, TypeError, AttributeError):
                continue
        with self._lock:
            self._targets = valid
            self._threads = {k: v for k, v in self._threads.items() if k in valid}

    def snapshot(self):
        with self._lock:
            return copy.deepcopy({"source": "codex_desktop_ipc", "connected": self._connected,
                                  "error": self._error, "last_message_at": self._last_message_at,
                                  "threads": self._threads})

    def close(self):
        self._stop.set()
        sock = self._sock
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self._worker.join(timeout=2)

    def _send(self, message):
        data = json.dumps(message, separators=(",", ":")).encode("utf-8")
        self._sock.sendall(struct.pack("<I", len(data)) + data)

    def _request(self, method, params, version=0, thread_id=None):
        request_id = str(uuid.uuid4())
        self._pending[request_id] = (method, thread_id)
        self._send({"type": "request", "requestId": request_id, "sourceClientId": self._client,
                    "version": version, "method": method, "params": params, "timeoutMs": 2000})

    def _follow(self, thread_id, owner, following):
        self._send({"type": "broadcast", "method": "thread-stream-following-changed",
                    "sourceClientId": self._client, "targetClientIds": [owner], "version": 1,
                    "params": {"hostId": "local", "conversationId": thread_id, "following": following}})

    def _resnapshot(self, thread_id):
        # Retain last published metadata only as stale evidence. No heartbeat may
        # make it current again until a new authoritative full snapshot arrives.
        self._states.pop(thread_id, None)
        self._revisions.pop(thread_id, None)
        owner = self._owners.get(thread_id)
        if owner:
            self._follow(thread_id, owner, False)
            self._follow(thread_id, owner, True)

    def _run(self):
        while not self._stop.is_set():
            try:
                # Do not follow symlinks to arbitrary sockets owned by another user.
                st = os.lstat(self.socket_path)
                if st.st_uid != os.getuid():
                    raise PermissionError("socket owner mismatch")
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._sock.settimeout(0.25)
                self._sock.connect(self.socket_path)
                self._client = "initializing-client"
                self._pending, self._owners, self._states, self._revisions = {}, {}, {}, {}
                self._request("initialize", {"clientType": "rotating-flower-observer"})
                buf, refreshed = bytearray(), float("-inf")
                while not self._stop.is_set():
                    now = time.monotonic()
                    with self._lock:
                        targets = set(self._targets)
                    if self._client != "initializing-client" and now - refreshed >= self.refresh_seconds:
                        for tid, owner in list(self._owners.items()):
                            if tid not in targets:
                                self._follow(tid, owner, False)
                                self._owners.pop(tid, None)
                                self._states.pop(tid, None)
                                self._revisions.pop(tid, None)
                        for tid in targets:
                            self._request("thread-owner-discovery", {"hostId": "local", "conversationId": tid}, 1, tid)
                        refreshed = now
                    try:
                        data = self._sock.recv(65536)
                    except socket.timeout:
                        continue
                    if not data:
                        raise EOFError("desktop disconnected")
                    buf.extend(data)
                    while len(buf) >= 4:
                        length = struct.unpack_from("<I", buf)[0]
                        if length > 64 * 1024 * 1024:
                            raise ValueError("oversize IPC frame")
                        if len(buf) < 4 + length:
                            break
                        frame = json.loads(bytes(buf[4:4 + length]))
                        del buf[:4 + length]
                        self._handle(frame, targets)
            except (OSError, ValueError, EOFError, KeyError, TypeError, IndexError) as exc:
                with self._lock:
                    self._connected = False
                    self._error = type(exc).__name__
            finally:
                if self._sock:
                    self._sock.close()
                    self._sock = None
            self._stop.wait(self.reconnect_seconds)

    def _handle(self, message, targets):
        with self._lock:
            self._last_message_at = time.time()
        if message.get("type") == "client-discovery-request":
            self._send({"type": "client-discovery-response", "requestId": message["requestId"],
                        "response": {"canHandle": False}})
            return
        if message.get("type") == "response":
            method, tid = self._pending.pop(message.get("requestId"), (None, None))
            if method == "initialize":
                if message.get("resultType") != "success":
                    raise PermissionError("observer initialization rejected")
                self._client = message["result"]["clientId"]
                with self._lock:
                    self._connected, self._error = True, None
            elif method == "thread-owner-discovery" and tid in targets:
                if message.get("resultType") == "success":
                    owner = message["handledByClientId"]
                    if self._owners.get(tid) == owner and tid in self._states:
                        # Same owner replied over the live ordered IPC connection.
                        # Keep its subscription; avoid repeated full history snapshots.
                        with self._lock:
                            if tid in self._threads:
                                self._threads[tid]["observed_at"] = time.time()
                                self._threads[tid]["owner_found"] = True
                        return
                    if tid in self._owners:
                        self._follow(tid, self._owners[tid], False)
                    self._states.pop(tid, None)
                    self._revisions.pop(tid, None)
                    self._owners[tid] = owner
                    self._follow(tid, owner, True)
                else:
                    self._owners.pop(tid, None)
                    self._states.pop(tid, None)
                    self._revisions.pop(tid, None)
                    with self._lock:
                        previous = self._threads.get(tid, {"thread_id": tid, "host_id": "local"})
                        self._threads[tid] = {**previous, "owner_found": False, "owner_checked_at": time.time()}
            return
        if message.get("type") != "broadcast":
            return
        params = message.get("params", {})
        tid = params.get("conversationId")
        if tid not in targets or params.get("hostId", "local") != "local":
            return
        if message.get("method") == "thread-archived":
            if message.get("sourceClientId") != self._owners.get(tid):
                return
            with self._lock:
                self._threads[tid] = {**self._threads.get(tid, {}), "thread_id": tid,
                                      "host_id": "local", "archived": True, "observed_at": time.time()}
            return
        if message.get("method") == "thread-unarchived":
            if message.get("sourceClientId") == self._owners.get(tid):
                with self._lock:
                    if tid in self._threads:
                        self._threads[tid]["archived"] = False
            return
        if message.get("method") != "thread-stream-state-changed":
            return
        if message.get("sourceClientId") != self._owners.get(tid):
            return
        change = params.get("change", {})
        revision = change.get("revision")
        if type(revision) is not int or revision < 0:
            self._resnapshot(tid)
            return
        if change.get("type") == "snapshot":
            source = change.get("conversationState", {})
            if source.get("id") != tid or source.get("hostId", "local") != "local":
                self._resnapshot(tid)
                return
            candidate = {k: copy.deepcopy(v) for k, v in source.items() if k in WATCH_FIELDS}
        elif change.get("type") == "patches":
            base = change.get("baseRevision")
            if type(base) is not int or base < 0 or revision <= base or tid not in self._states or base != self._revisions.get(tid):
                self._resnapshot(tid)
                return
            try:
                candidate = apply_metadata_patches(self._states[tid], change.get("patches", []))
            except (ValueError, KeyError, TypeError, IndexError):
                self._resnapshot(tid)
                return
        else:
            return
        if candidate.get("id") != tid or candidate.get("hostId", "local") != "local":
            self._resnapshot(tid)
            return
        try:
            normalized = normalize_metadata(tid, candidate, time.time())
        except (ValueError, TypeError):
            self._resnapshot(tid)
            return
        if normalized["parent_thread_id"] is not None:
            self._states.pop(tid, None)
            self._revisions.pop(tid, None)
            return  # Only root chats belong to the physical desk indicator.
        self._states[tid] = candidate
        self._revisions[tid] = revision
        with self._lock:
            if self._threads.get(tid, {}).get("archived"):
                normalized["archived"] = True
            self._threads[tid] = normalized


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--thread-id", action="append", required=True)
    parser.add_argument("--seconds", type=float, default=3)
    args = parser.parse_args()
    feed = DesktopRuntimeFeed()
    feed.set_targets(args.thread_id)
    try:
        time.sleep(max(0.1, min(args.seconds, 30)))
        print(json.dumps(feed.snapshot(), ensure_ascii=False, indent=2))
    finally:
        feed.close()
