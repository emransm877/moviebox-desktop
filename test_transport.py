import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from media_bridge import MediaBridge
from downloads import Download


DATA = bytes(range(256)) * 2048


class Origin(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.headers.get('X-Test-Signature') != 'test-only':
            self.send_error(403)
            return
        start, end = 0, len(DATA) - 1
        partial = self.headers.get('Range')
        if partial:
            left, right = partial.removeprefix('bytes=').split('-', 1)
            start, end = int(left), int(right) if right else end
        self.send_response(206 if partial else 200)
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Accept-Ranges', 'bytes')
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{len(DATA)}')
        self.end_headers()
        self.wfile.write(DATA[start:end+1])


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.origin = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
        cls.thread = threading.Thread(target=cls.origin.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.origin.server_port}/sample.mp4'

    @classmethod
    def tearDownClass(cls):
        cls.origin.shutdown()
        cls.origin.server_close()

    def test_bridge_preserves_signed_headers_and_byte_ranges(self):
        bridge = MediaBridge()
        try:
            local = bridge.register(self.url, {'X-Test-Signature': 'test-only'})
            with urlopen(Request(local, headers={'Range': 'bytes=1024-4095'})) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), DATA[1024:4096])
                self.assertEqual(response.headers['Content-Range'], f'bytes 1024-4095/{len(DATA)}')
            with self.assertRaises(HTTPError):
                urlopen(local.rsplit('/', 1)[0] + '/unknown.mp4')
        finally:
            bridge.close()

    def test_download_resumes_partial_file_without_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.mp4'
            path.with_suffix('.mp4.part').write_bytes(DATA[:12345])
            task = Download(self.url, path, {'X-Test-Signature': 'test-only'})
            task.run()
            self.assertEqual(task.status, 'Complete')
            self.assertEqual(path.read_bytes(), DATA)
            self.assertFalse(path.with_suffix('.mp4.part').exists())


if __name__ == '__main__':
    unittest.main()
