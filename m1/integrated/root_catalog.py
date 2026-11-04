"""Header-only local root-chat discovery; never load old conversation bodies."""
import json
import time
from pathlib import Path
from motor_bridge_base import is_root_meta


class RootCatalog:
    def __init__(self, root):
        self.root = Path(root)
        self.known = {}
        self.next_scan = 0

    def poll(self, now=None):
        now = time.monotonic() if now is None else now
        if now < self.next_scan:
            return
        self.next_scan = now + 5
        present = set()
        for path in self.root.rglob('rollout-*.jsonl'):
            present.add(path)
            try:
                inode = path.stat().st_ino
                if path in self.known and self.known[path][0] == inode:
                    continue
                with path.open('rb') as f:
                    first = f.readline(1_000_001)
                if not first.endswith(b'\n') or len(first) > 1_000_000:
                    continue
                meta = json.loads(first)
                identity = meta['payload']['id'] if is_root_meta(meta) else None
                self.known[path] = (inode, identity)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        self.known = {p: v for p, v in self.known.items() if p in present}

    @property
    def ids(self):
        return {identity for _, identity in self.known.values() if identity}
