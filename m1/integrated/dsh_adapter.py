"""Read the bounded heartbeat produced by our local DSH observer plugin."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import sys

# process_probe lives one directory up, shared with the other bridges.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import process_probe

RANK = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'XHIGH': 4, 'ULTRA': 5}

def process_alive(pid):
    """POSIX uses os.kill(pid, 0); Windows uses OpenProcess via process_probe.

    os.kill maps to TerminateProcess on Windows, so probing there would kill
    the process instead of checking it.
    """
    try:
        return process_probe.process_alive(pid)
    except PermissionError:
        return True

def speed_for_effort(effort):
    if effort is None:
        return 'LOW'
    return {'off': 'LOW', 'none': 'LOW', 'minimal': 'LOW', 'low': 'MEDIUM',
            'medium': 'MEDIUM', 'high': 'HIGH', 'xhigh': 'XHIGH', 'max': 'ULTRA'}.get(effort.lower(), 'HIGH')

class DshAdapter:
    MAX_BYTES = 1024 * 1024
    def __init__(self, path=None):
        self.path = Path(path or Path.home() / 'Library/Application Support/RotatingFlower/dsh/status.json')

    def quiet(self, readiness, error=None):
        return {'healthy': False, 'readiness': readiness, 'error': error,
                'detail': '打开 DeepSeek Harness；若已打开，请重启一次以加载小花插件。',
                'motor': 'STOP', 'light': False, 'working_threads': [],
                'waiting_threads': [], 'pending_questions': 0}

    def poll(self, now):
        try:
            with self.path.open('rb') as f:
                raw = f.read(self.MAX_BYTES + 1)
            if len(raw) > self.MAX_BYTES:
                raise ValueError('oversized metadata')
            d = json.loads(raw)
            if not isinstance(d, dict) or d.get('schema') != 1:
                raise ValueError('unsupported schema')
            stamp = d.get('updated_at')
            if type(stamp) not in (int, float) or not math.isfinite(stamp):
                raise ValueError('invalid heartbeat')
            if not -2 <= now - stamp < 3:
                return self.quiet('not_running')
            if d.get('error'):
                return self.quiet('error', 'DSH task metadata is incompatible')
            if d.get('connected') is not True:
                return self.quiet('not_running')
            pid = d.get('pid')
            if type(pid) is not int or pid <= 0:
                raise ValueError('invalid process')
            if not process_alive(pid):
                return self.quiet('not_running')
            tasks = d.get('tasks')
            if not isinstance(tasks, list) or len(tasks) > 4096:
                raise ValueError('invalid tasks')
            working, waiting, speeds, pending = [], [], [], 0
            seen = set()
            for t in tasks:
                if not isinstance(t, dict) or not isinstance(t.get('id'), str) or t['id'] in seen:
                    raise ValueError('invalid task identity')
                seen.add(t['id'])
                if any(type(t.get(k)) is not bool for k in ('running', 'blocking')):
                    raise ValueError('invalid task flags')
                if any(type(t.get(k)) is not int or t[k] < 0 for k in ('questions', 'approvals')):
                    raise ValueError('invalid attention counts')
                if t.get('effort') is not None and not isinstance(t['effort'], str):
                    raise ValueError('invalid effort')
                if t['questions'] or t['approvals']:
                    waiting.append(t['id']); pending += t['questions'] + t['approvals']
                if t['running'] and not t['blocking']:
                    working.append(t['id']); speeds.append(speed_for_effort(t.get('effort')))
            return {'healthy': True, 'readiness': 'ready', 'error': None,
                    'motor': 'RUN ' + max(speeds, key=RANK.get) if speeds else 'STOP',
                    'light': bool(waiting), 'working_threads': working,
                    'waiting_threads': waiting, 'pending_questions': pending}
        except FileNotFoundError:
            return self.quiet('not_initialized')
        except (OSError, ValueError, TypeError, KeyError):
            return self.quiet('error', 'DSH metadata is not readable or invalid')

    def close(self):
        pass
