"""Small theme tokens shared by the native shell and its custom painters."""
import json
from pathlib import Path
# Shared with the TV implementation; legacy IDs retain their colour identity.
THEME_SPEC = json.loads((Path(__file__).parent/'assets'/'theme-spec-20.json').read_text(encoding='utf-8'))
THEMES = {record['id']:dict(record['palette']) for record in THEME_SPEC['themes']}
THEME_EFFECTS = {record['id']:record['geometry'] for record in THEME_SPEC['themes']}

def theme_key(value):
    return value if isinstance(value, str) and value in THEMES else 'obsidian'

def initial_theme(state, system_dark=True):
    if state.get('appearance') == 'system':
        return 'obsidian' if system_dark else 'aurora'
    if isinstance(state.get('theme'), str) and state['theme'] in THEMES:
        return state['theme']
    mode = state.get('appearance', 'dark')
    return 'aurora' if mode == 'light' or (mode == 'system' and not system_dark) else 'obsidian'

def palette(value):
    # Booleans remain supported by existing smoke/appearance integrations.
    return THEMES['obsidian' if value is True else 'aurora' if value is False else theme_key(value)]
