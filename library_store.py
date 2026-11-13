"""Durable library snapshots with recovery and merging across app instances."""
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import tempfile
import time

MISSING = object()


def valid_state(value):
    if not isinstance(value, dict):
        raise ValueError('Library must be an object')
    for field in ('history', 'saved'):
        if not isinstance(value.get(field, {}), dict):
            raise ValueError('Invalid library collection')
    return value


def apply_changes(current, before, after, path=()):
    """Apply only this instance's changes; retain other instances' newer progress."""
    result = copy.deepcopy(current)
    for key in before.keys() | after.keys():
        old, new = before.get(key, MISSING), after.get(key, MISSING)
        if old == new:
            continue
        if new is MISSING:
            result.pop(key, None)
        elif isinstance(new, dict) and isinstance(old, dict) and isinstance(result.get(key), dict):
            if path == ('history',) and float(result[key].get('updated') or 0) > float(new.get('updated') or 0):
                continue
            result[key] = apply_changes(result[key], old, new, path + (key,))
        elif path == ('history',) and isinstance(new, dict) and isinstance(result.get(key), dict) and float(result[key].get('updated') or 0) > float(new.get('updated') or 0):
            continue
        else:
            result[key] = copy.deepcopy(new)
    return result


class LibraryStore:
    def __init__(self, path):
        self.path = Path(path)
        self.backup = self.path.with_suffix(self.path.suffix + '.bak')
        self.before = {'saved': {}, 'history': {}}
        self.recovered = False

    def read(self):
        for index, file in enumerate((self.path, self.backup)):
            try:
                value = valid_state(json.loads(file.read_text(encoding='utf-8-sig')))
                self.recovered = index == 1
                return {'saved': {}, 'history': {}, **value}
            except (OSError, ValueError, TypeError):
                pass
        return {'saved': {}, 'history': {}}

    def load(self):
        value = self.read()
        self.before = copy.deepcopy(value)
        return value

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a+b') as stream:
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b'0'); stream.flush()
            deadline = time.monotonic() + 1
            while True:
                try:
                    stream.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise OSError('Another MovieBox instance is saving. Please retry.')
                    time.sleep(.02)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    @staticmethod
    def atomic_write(file, value):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=file.parent, prefix=file.name + '.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(value, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            for attempt in range(4):
                try:
                    os.replace(temporary, file)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
                    time.sleep(.02 * (attempt + 1))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def save(self, value):
        valid_state(value)
        with self.locked():
            current = self.read()
            merged = apply_changes(current, self.before, value)
            self.atomic_write(self.path, merged)
            self.atomic_write(self.backup, merged)
            self.before = copy.deepcopy(value)
            return merged
