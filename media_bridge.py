"""Loopback, capability-protected media transport for the native player.

Only exact sources registered by the app are served. There is no URL proxy API.
Preserves the service's own signed media headers and HTTP byte ranges.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import secrets
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class MediaBridge:
    def __init__(self):
        self.token = secrets.token_urlsafe(24)
        self.sources = {}
        self.lock = threading.Lock()
        self.bytes_received, self.read_seconds, self.http_error = 0, 0, 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self.transfer(True)

            def do_GET(self):
                self.transfer(False)

            def transfer(self, head):
                with owner.lock:
                    source = owner.sources.get(self.path)
                if not source:
                    self.send_error(404)
                    return
                url, headers = source
                headers = dict(headers)
                if self.headers.get('Range'):
                    headers['Range'] = self.headers['Range']
                try:
                    request = Request(url, headers=headers, method='HEAD' if head else 'GET')
                    with urlopen(request, timeout=15) as upstream:
                        self.send_response(upstream.status)
                        for name in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'Last-Modified', 'ETag']:
                            if upstream.headers.get(name):
                                self.send_header(name, upstream.headers[name])
                        self.send_header('Connection', 'close')
                        self.end_headers()
                        if not head:
                            while True:
                                started = time.monotonic()
                                data = upstream.read(65536)
                                elapsed = time.monotonic() - started
                                if not data:
                                    break
                                with owner.lock:
                                    owner.bytes_received += len(data)
                                    owner.read_seconds += elapsed
                                self.wfile.write(data)
                except HTTPError as error:
                    owner.http_error = error.code
                    self.send_error(error.code)
                except (ConnectionError, BrokenPipeError, TimeoutError, OSError):
                    self.close_connection = True
                self.close_connection = True

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name='moviebox-media')
        self.thread.start()

    def register(self, url, headers=None):
        key = '/' + self.token + '/' + secrets.token_urlsafe(12) + '.mp4'
        with self.lock:
            self.sources[key] = (url, headers or {'User-Agent': 'Mozilla/5.0'})
            # Keep enough previous entries for an in-flight seek during a switch.
            while len(self.sources) > 8:
                del self.sources[next(iter(self.sources))]
            self.http_error = 0
        return f'http://127.0.0.1:{self.server.server_port}{key}'

    def bandwidth_mbps(self):
        with self.lock:
            return self.bytes_received * 8 / max(.05, self.read_seconds) / 1_000_000

    def close(self):
        self.server.shutdown()
        self.server.server_close()
