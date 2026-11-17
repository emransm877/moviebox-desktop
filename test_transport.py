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
STALLED = threading.Event()
RELEASE = threading.Event()


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
        if self.path == '/stall.mp4':
            self.wfile.flush();STALLED.set();RELEASE.wait(5)
            try:self.wfile.write(DATA[start:end+1])
            except (OSError,ConnectionError):pass
            return
        self.wfile.write(DATA[start:end+1])


class TransportTests(unittest.TestCase):
    def test_loopback_startup_never_calls_blocking_reverse_dns(self):
        from unittest.mock import patch
        with patch('socket.getfqdn',side_effect=AssertionError('Unexpected reverse DNS on the GUI thread')):
            bridge=MediaBridge()
            try:self.assertEqual(bridge.server.server_name,'localhost')
            finally:bridge.close()
    def test_cancelling_loopback_unblocks_read_without_waiting_for_origin(self):
        import time
        bridge=MediaBridge();STALLED.clear();RELEASE.clear();finished=threading.Event();errors=[]
        local=bridge.register(self.url.replace('/sample.mp4','/stall.mp4'),{'X-Test-Signature':'test-only'})
        def read():
            try:
                with urlopen(local,timeout=4) as response:response.read()
            except Exception as error:errors.append(type(error).__name__)
            finally:finished.set()
        worker=threading.Thread(target=read,daemon=True);worker.start()
        try:
            self.assertTrue(STALLED.wait(2),'Fixture origin did not begin stalled response')
            started=time.monotonic();bridge.cancel_active()
            self.assertTrue(finished.wait(.75),'Player-side read waited for the stalled upstream')
            self.assertLess(time.monotonic()-started,.75);self.assertTrue(errors)
            fresh=bridge.register(self.url,{'X-Test-Signature':'test-only'})
            with urlopen(fresh,timeout=2) as response:self.assertEqual(response.read(),DATA)
        finally:RELEASE.set();worker.join(2);bridge.close()
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
