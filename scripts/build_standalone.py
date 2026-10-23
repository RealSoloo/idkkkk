"""Bundle game modules for executors that cannot access the GitHub repository.
Run after changing Soloshub.txt or any game module. No uploaded code is executed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = {'mm2': 'Mm2.txt', 'arsenal': 'Arsenal.txt', 'pf': 'Pf.txt',
           'lt2': 'Lt2.txt', 'doomspire': 'Doomspire.txt', 'bab': 'Bab.txt'}
MARKER = '\t-- everything a game script can use from this file'


def lua_string(source):
    equals = '=='
    while ']' + equals + ']' in source:
        equals += '='
    # Lua discards the first newline after the long-string opening delimiter.
    return '[' + equals + '[\n' + source + ']' + equals + ']'


def build():
    source = ROOT.joinpath('Soloshub.txt').read_text()
    entries = ['\t-- Generated bundled modules: rebuild with scripts/build_standalone.py.',
               '\tHub.BundledModules = {']
    for key, file in MODULES.items():
        entries.append('\t\t' + key + ' = ' + lua_string(ROOT.joinpath(file).read_text()) + ',')
    entries.append('\t}\n\n')
    assert source.count(MARKER) == 1
    source = source.replace(MARKER, '\n'.join(entries) + MARKER, 1)
    return '-- GENERATED standalone hub: all six game modules included locally.\n' + source


if __name__ == '__main__':
    path = ROOT / 'SoloshubStandalone.txt'
    path.write_bytes(build().encode('utf-8'))
    print(f'Built {path.name} ({path.stat().st_size:,} bytes)')
