"""Small theme tokens shared by the native shell and its custom painters."""
THEMES = {
    'obsidian': dict(name='Obsidian Cinema', description='Cinematic charcoal with mint highlights.', dark=True, layout='sidebar', accent='#48e6b0', ink='#08251a', base='#090e12', panel='#10181e', surface='#19242c', hover='#26393e', text='#f0f5f7', secondary='#a2b3be', line='#2c3e46', field='#17232b', select='#204238', hero='#09191d'),
    'orbital': dict(name='Orbital', description='Midnight blue, ice-blue accents and a top navigation bar.', dark=True, layout='top', accent='#57d9ff', ink='#062536', base='#070f20', panel='#101c30', surface='#172940', hover='#223d58', text='#edf6ff', secondary='#a1b7d0', line='#2c4763', field='#13253b', select='#193e59', hero='#08172a'),
    'prism': dict(name='Prism', description='Indigo and violet with a compact navigation rail.', dark=True, layout='rail', accent='#bf83ff', ink='#210d38', base='#100c20', panel='#19142f', surface='#281e42', hover='#3a2c5b', text='#f6f0ff', secondary='#beafd2', line='#48365e', field='#241b3b', select='#432d61', hero='#1e1038'),
    'aurora': dict(name='Aurora', description='Pearl surfaces, emerald accents and an airy editorial layout.', dark=False, layout='top', accent='#087f5b', ink='#ffffff', base='#edf3f0', panel='#fafcfb', surface='#ffffff', hover='#e4f0e9', text='#142b23', secondary='#526e62', line='#c8dcd2', field='#ffffff', select='#d3ebdf', hero='#eff6f1'),
    'eclipse': dict(name='Eclipse', description='Cinema black, champagne gold and elegant display typography.', dark=True, layout='top', accent='#edc47f', ink='#2a1b08', base='#100e0b', panel='#18150f', surface='#252017', hover='#393022', text='#fbf2df', secondary='#c5b394', line='#4c402d', field='#221d15', select='#493923', hero='#21180d'),
}

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
