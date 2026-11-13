"""Stable source names, with legacy 'both' (Codex + WorkBuddy) aliases."""
from itertools import combinations

NAMES = ('codex', 'workbuddy', 'dsh', 'qodercn')
LABELS = {'codex': 'Codex', 'workbuddy': 'WorkBuddy', 'dsh': 'DeepSeek Harness',
          'qodercn': 'Qoder CN'}
# 'all' keeps its historical meaning so an existing installation upgrade does
# not start reporting a new, never-initialized source. Qoder CN is opt-in.
LEGACY_ALL = ('codex', 'workbuddy', 'dsh')
_SUBSETS = tuple(','.join(combo) for size in range(1, len(NAMES) + 1)
                 for combo in combinations(NAMES, size))
CHOICES = ('both', 'all') + _SUBSETS


def enabled_sources(source):
    if source == 'all':
        return LEGACY_ALL
    if source == 'both':
        return ('codex', 'workbuddy')
    if not isinstance(source, str) or not source:
        raise ValueError('Unknown source selection')
    parts = tuple(source.split(','))
    if len(set(parts)) != len(parts) or any(part not in NAMES for part in parts):
        raise ValueError('Unknown source selection')
    return parts


def selection_for(names):
    selected = tuple(n for n in NAMES if n in names)
    if selected == LEGACY_ALL:
        return 'all'
    if selected == ('codex', 'workbuddy'):
        return 'both'
    if not selected:
        raise ValueError('No supported applications')
    return ','.join(selected)