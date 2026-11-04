"""Pure status fusion for the flower: work drives rotation, waits drive light.

No I/O, clock calls, serial access, or Codex internals live here. Inputs are
validated metadata from adapters. All timestamps and ``now`` must use the same
clock (the rollout adapter currently uses Unix seconds).

Runtime snapshots must describe the *existing desktop chat*, not a second
app-server process. ``observed_at`` means a successful current status read, or a
cached status revalidated by a healthy subscription, not merely the last time
the reducer ran. The provider must establish that waiting flags mean the chat
is blocked before enabling runtime overrides.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping


EFFORT_SPEED = {
    "none": "LOW", "minimal": "LOW", "low": "LOW",
    "medium": "MEDIUM", "high": "HIGH", "xhigh": "XHIGH",
    "max": "ULTRA", "ultra": "ULTRA",
}
SPEED_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "XHIGH": 4, "ULTRA": 5}
WAIT_FLAGS = frozenset(("waitingOnApproval", "waitingOnUserInput"))


@dataclass(frozen=True)
class RolloutSnapshot:
    thread_id: str
    active: bool
    effort: str | None
    updated_at: float
    started_at: float = 0.0
    is_root: bool = True


@dataclass(frozen=True)
class RuntimeSnapshot:
    thread_id: str
    status_type: str
    observed_at: float
    # None means absent/unrecognised metadata, distinct from confirmed [].
    active_flags: tuple[str, ...] | None = None
    # Root metadata may instead come from the matching rollout.
    is_root: bool = False

    @classmethod
    def from_status(cls, thread_id: str, status: object, observed_at: float,
                    *, is_root: bool = False) -> RuntimeSnapshot:
        """Read only the documented status fields; missing flags stay unknown."""
        if not isinstance(status, Mapping):
            return cls(thread_id, "unknown", observed_at, is_root=is_root)
        kind = status.get("type")
        kind = kind if isinstance(kind, str) else "unknown"
        raw_flags = status.get("activeFlags")
        flags = (tuple(raw_flags) if isinstance(raw_flags, (list, tuple))
                 and all(isinstance(flag, str) for flag in raw_flags) else None)
        return cls(thread_id, kind, observed_at, flags, is_root)


@dataclass(frozen=True)
class FlowerState:
    motor_command: str
    selected_thread: str | None
    working_threads: tuple[str, ...]
    waiting_threads: tuple[str, ...]
    light: bool
    pending_question_count: int
    # A degraded thread is using rollout activity because live status is unknown.
    degraded_threads: tuple[str, ...]
    sources: tuple[tuple[str, str], ...]

    @property
    def working_count(self) -> int:
        return len(self.working_threads)


def _fresh(stamp: float, now: float, ttl: float, future_skew: float) -> bool:
    # NaN and infinity also fail these comparisons.
    return -future_skew <= now - stamp < ttl


def reduce_state(
    rollouts: Iterable[RolloutSnapshot],
    runtimes: Iterable[RuntimeSnapshot] = (),
    pending_async: Iterable[tuple[str, str, int]] = (),
    *,
    now: float,
    runtime_ttl: float = 5.0,
    rollout_ttl: float = 600.0,
    future_skew: float = 2.0,
    fallback_policy: str = "stop",
) -> FlowerState:
    """Select independent motor/light outputs without changing any input.

    Fresh runtime ``idle`` wins over old rollout activity. Fresh runtime
    ``active`` with explicit [] is working; recognised waiting flags mean
    blocked. Missing, stale, notLoaded, erroneous or unknown statuses are
    labelled degraded. An unfamiliar active flag is unknown, never silently
    treated as evidence of work or a blocking wait.

    ``fallback_policy`` is explicit: ``stop`` (default) fails quiet when runtime
    is unknown; ``rollout`` reproduces legacy start/end-only behaviour;
    ``hold_wait`` uses rollout fallback except that a stale, previously known
    waiting snapshot keeps that chat stopped and the light on. ``hold_wait``
    has no timeout: the provider must remove or replace the snapshot on close,
    answer, cancellation, or its own feed-loss policy. A rollout cannot reveal
    a live approval, so legacy fallback is intentionally marked degraded.

    ``pending_async`` must come from the validated root-chat question adapter;
    those keys affect light only. They remain valid when their originating
    assistant turn completes. Their expiry and resolution belong to that
    adapter, not this reducer.
    """
    if runtime_ttl <= 0 or rollout_ttl <= 0 or future_skew < 0:
        raise ValueError("TTLs must be positive and future_skew non-negative")
    if fallback_policy not in ("stop", "rollout", "hold_wait"):
        raise ValueError("fallback_policy must be stop, rollout or hold_wait")

    rollout_by_id: dict[str, RolloutSnapshot] = {}
    runtime_by_id: dict[str, RuntimeSnapshot] = {}
    for item in rollouts:
        if not item.thread_id or not item.is_root:
            continue
        old = rollout_by_id.get(item.thread_id)
        # Duplicate rollout files represent one chat. At equal timestamps an
        # explicit inactive record takes priority rather than reviving motion.
        if old is None or (item.updated_at, not item.active) > (old.updated_at, not old.active):
            rollout_by_id[item.thread_id] = item
    for item in runtimes:
        if not item.thread_id or not (item.is_root or item.thread_id in rollout_by_id):
            continue
        old = runtime_by_id.get(item.thread_id)
        if old is None or item.observed_at > old.observed_at:
            runtime_by_id[item.thread_id] = item

    working: list[tuple[str, str, float]] = []
    waiting: list[str] = []
    degraded: list[str] = []
    sources: list[tuple[str, str]] = []
    for thread in sorted(rollout_by_id.keys() | runtime_by_id.keys()):
        rollout = rollout_by_id.get(thread)
        runtime = runtime_by_id.get(thread)
        live_kind = None
        if runtime and _fresh(runtime.observed_at, now, runtime_ttl, future_skew):
            if runtime.status_type == "idle":
                live_kind = "idle"
            elif (runtime.status_type == "active" and runtime.active_flags is not None
                  and set(runtime.active_flags) <= WAIT_FLAGS):
                live_kind = "waiting" if runtime.active_flags else "working"
        if live_kind is not None:
            sources.append((thread, "runtime:" + live_kind))
            active = live_kind == "working"
            if live_kind == "waiting":
                waiting.append(thread)
        else:
            degraded.append(thread)
            hold_wait = bool(
                fallback_policy == "hold_wait" and runtime
                and math.isfinite(runtime.observed_at)
                and runtime.observed_at <= now + future_skew
                and runtime.status_type == "active" and runtime.active_flags
                and set(runtime.active_flags) <= WAIT_FLAGS)
            if hold_wait:
                active = False
                waiting.append(thread)
                sources.append((thread, "fallback:held_wait"))
            elif fallback_policy == "stop":
                active = False
                sources.append((thread, "fallback:stopped"))
            else:
                active = bool(rollout and rollout.active
                              and _fresh(rollout.updated_at, now, rollout_ttl, future_skew))
                sources.append((thread, "rollout:working" if active else "rollout:idle_or_stale"))
        if active:
            effort = rollout.effort if rollout else None
            speed = EFFORT_SPEED.get(effort.lower() if isinstance(effort, str) else "", "MEDIUM")
            working.append((thread, speed, rollout.started_at if rollout else 0.0))

    # A wait cannot choose the motor speed. Tie breaking matches the previous
    # bridge's preference for the most recently started task, then is stable.
    selected = max(working, key=lambda row: (SPEED_RANK[row[1]], row[2], row[0])) if working else None
    question_count = len(set(pending_async))
    return FlowerState(
        motor_command="RUN " + selected[1] if selected else "STOP",
        selected_thread=selected[0] if selected else None,
        working_threads=tuple(row[0] for row in working),
        waiting_threads=tuple(waiting),
        light=bool(waiting or question_count),
        pending_question_count=question_count,
        degraded_threads=tuple(degraded),
        sources=tuple(sources),
    )
