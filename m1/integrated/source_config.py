"""Stable source names, including legacy 'both' (Codex + WorkBuddy)."""
NAMES = ('codex', 'workbuddy', 'dsh')
LABELS = {'codex': 'Codex', 'workbuddy': 'WorkBuddy', 'dsh': 'DeepSeek Harness'}
CHOICES = ('codex', 'workbuddy', 'both', 'dsh', 'codex,dsh', 'workbuddy,dsh', 'all')

def enabled_sources(source):
    if source not in CHOICES:
        raise ValueError('Unknown source selection')
    return NAMES if source == 'all' else ('codex', 'workbuddy') if source == 'both' else tuple(source.split(','))

def selection_for(names):
    selected = tuple(n for n in NAMES if n in names)
    if selected == NAMES:
        return 'all'
    if selected == ('codex', 'workbuddy'):
        return 'both'
    if not selected:
        raise ValueError('No supported applications')
    return ','.join(selected)
