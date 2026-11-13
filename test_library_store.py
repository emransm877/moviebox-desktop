import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from library_store import LibraryStore


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'library.json'

    def test_fresh_install_round_trip_and_latest_backup(self):
        store = LibraryStore(self.path)
        state = store.load()
        state['history']['movie:0:0'] = {'position': 2400, 'updated': 1}
        store.save(state)
        self.assertEqual(LibraryStore(self.path).load(), state)
        self.assertEqual(json.loads(store.backup.read_text()), state)

    def test_idle_second_instance_does_not_erase_playback(self):
        first, second = LibraryStore(self.path), LibraryStore(self.path)
        a, b = first.load(), second.load()
        a['history']['movie:0:0'] = {'position': 90000, 'updated': 2}
        first.save(a)
        b['appearance'] = 'dark'
        second.save(b)
        restored = LibraryStore(self.path).load()
        self.assertEqual(restored['history'], a['history'])
        self.assertEqual(restored['appearance'], 'dark')

    def test_outdated_instance_cannot_move_progress_backwards(self):
        original = LibraryStore(self.path)
        state = original.load()
        state['history']['movie'] = {'position': 9000, 'updated': 1}
        original.save(state)
        first, second = LibraryStore(self.path), LibraryStore(self.path)
        a, b = first.load(), second.load()
        a['history']['movie'] = {'position': 30000, 'updated': 3}
        first.save(a)
        b['history']['movie'] = {'position': 12000, 'updated': 2}
        second.save(b)
        self.assertEqual(LibraryStore(self.path).load()['history']['movie']['position'], 30000)

    def test_removing_saved_title_does_not_resurrect_it(self):
        store = LibraryStore(self.path)
        state = store.load()
        state['saved']['movie'] = {'subjectId': 'movie'}
        store.save(state)
        idle = LibraryStore(self.path)
        stale = idle.load()
        state['saved'].pop('movie')
        store.save(state)
        stale['appearance'] = 'light'
        idle.save(stale)
        self.assertEqual(LibraryStore(self.path).load()['saved'], {})

    def test_truncated_library_recovers_history_from_backup(self):
        store = LibraryStore(self.path)
        state = store.load()
        state['history']['movie'] = {'position': 75000, 'updated': 2}
        store.save(state)
        self.path.write_text('{"history":')
        restored = LibraryStore(self.path)
        self.assertEqual(restored.load(), state)
        self.assertTrue(restored.recovered)
        restored.save(state)
        self.assertEqual(json.loads(self.path.read_text()), state)

    def test_transient_windows_sharing_violation_is_retried(self):
        store = LibraryStore(self.path)
        state = store.load()
        import os
        real = os.replace
        calls = []
        def sharing_once(source, destination):
            calls.append(destination)
            if len(calls) == 1:
                raise PermissionError('File scanner holds destination')
            return real(source, destination)
        with patch('library_store.os.replace', side_effect=sharing_once):
            store.save(state)
        self.assertEqual(LibraryStore(self.path).load(), state)
        self.assertFalse(list(self.path.parent.glob('*.tmp')))

    def test_failed_save_keeps_previous_history_and_reports_failure(self):
        store = LibraryStore(self.path)
        state = store.load()
        state['history']['movie'] = {'position': 1000, 'updated': 1}
        store.save(state)
        changed = copy.deepcopy(state)
        changed['history']['movie']['position'] = 2000
        with patch('library_store.os.replace', side_effect=PermissionError('Access denied')):
            with self.assertRaises(PermissionError):
                store.save(changed)
        self.assertEqual(LibraryStore(self.path).load(), state)


if __name__ == '__main__':
    unittest.main()
