"""Download failures must retain resumable bytes and never publish corrupt video."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from downloads import Download


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {'Content-Length': str(len(data))}


class DownloadSafetyTests(unittest.TestCase):
    def run_download(self, response, partial=b'old', cancel=False):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        target = Path(self.directory.name) / 'owned.mp4'
        part = target.with_suffix('.mp4.part')
        part.write_bytes(partial)
        task = Download('https://example.test/owned', target, {})
        if cancel:
            task.cancelled.set()
        with patch('downloads.urlopen', return_value=response):
            task.run()
        return task, target, part

    def test_server_ignoring_range_restarts_without_old_bytes(self):
        task, target, part = self.run_download(Response(b'fresh-video'))
        self.assertEqual(task.status, 'Complete')
        self.assertEqual(target.read_bytes(), b'fresh-video')
        self.assertFalse(part.exists())

    def test_wrong_range_cannot_be_marked_complete_or_destroy_partial(self):
        task, target, part = self.run_download(Response(b'xx', 206, {'Content-Length': '2', 'Content-Range': 'bytes 8-9/10'}))
        self.assertTrue(task.status.startswith('Error:'))
        self.assertFalse(target.exists())
        self.assertEqual(part.read_bytes(), b'old')

    def test_range_ending_before_file_end_is_not_complete(self):
        task, target, part = self.run_download(Response(b'xx', 206, {'Content-Length': '2', 'Content-Range': 'bytes 3-4/10'}))
        self.assertTrue(task.status.startswith('Error:'))
        self.assertFalse(target.exists())
        self.assertEqual(part.read_bytes(), b'old')

    def test_range_length_mismatch_preserves_partial(self):
        task, target, part = self.run_download(Response(b'xx', 206, {'Content-Length': '1', 'Content-Range': 'bytes 3-4/5'}))
        self.assertTrue(task.status.startswith('Error:'))
        self.assertFalse(target.exists())
        self.assertEqual(part.read_bytes(), b'old')

    def test_truncated_body_retains_part_without_complete_target(self):
        task, target, part = self.run_download(Response(b'short', headers={'Content-Length': '30'}))
        self.assertEqual(task.status, 'Interrupted')
        self.assertFalse(target.exists())
        self.assertEqual(part.read_bytes(), b'short')

    def test_pause_does_not_publish_incomplete_target(self):
        task, target, part = self.run_download(Response(b'bytes', 206, {'Content-Length': '5', 'Content-Range': 'bytes 3-7/8'}), cancel=True)
        self.assertEqual(task.status, 'Paused')
        self.assertFalse(target.exists())
        self.assertEqual(part.read_bytes(), b'old')

    def test_unwritable_parent_is_reported_as_download_error(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / 'file'
            parent.write_bytes(b'keep')
            task = Download('https://example.test/owned', parent/'owned.mp4', {})
            task.run()
            self.assertTrue(task.status.startswith('Error:'))
            self.assertEqual(parent.read_bytes(), b'keep')
