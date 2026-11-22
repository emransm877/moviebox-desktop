"""Loopback, capability-protected media transport for the native player.

Only exact sources registered by the app are served. There is no URL proxy API.
Preserves the service's own signed media headers and HTTP byte ranges.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
import secrets
import threading
import socket
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class LoopbackHTTPServer(ThreadingHTTPServer):
    def serve_forever(self, poll_interval=.1):
        try:
            super().serve_forever(poll_interval)
        except (OSError, ValueError):
            if self.socket.fileno() != -1:
                raise

    def server_bind(self):
        # HTTPServer otherwise performs reverse DNS synchronously at startup.
        # This server is always numeric loopback and needs no hostname lookup.
        TCPServer.server_bind(self)
        self.server_name = 'localhost'
        self.server_port = self.server_address[1]


class MediaBridge:
    def __init__(self):
        self.token = secrets.token_urlsafe(24)
        self.sources = {}
        self.lock = threading.Lock()
        self.clients = set()
        self.bytes_received, self.read_seconds, self.http_error = 0, 0, 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def setup(self):
                super().setup()
                with owner.lock: owner.clients.add(self.connection)

            def finish(self):
                try: super().finish()
                finally:
                    with owner.lock: owner.clients.discard(self.connection)

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

        self.handler_type = Handler
        self.server = None
        self.start_server()

    def start_server(self):
        self.server = LoopbackHTTPServer(('127.0.0.1', 0), self.handler_type)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name='moviebox-media')
        self.thread.start()

    def register(self, url, headers=None):
        if self.server is None:
            self.start_server()
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

    def cancel_active(self):
        """End downstream reads before Qt synchronously joins its media workers.

        Closing an upstream response may itself wait for its pending read.
        Retire the listener and shut down downstream sockets before player.stop;
        a late decoder retry must fail without a Python handler acquiring GIL.
        """
        with self.lock:
            clients = list(self.clients)
            self.sources.clear()
            server, self.server = self.server, None
        if server is not None:
            # A decoder may reconnect after the client snapshot above. Closing
            # the old listening socket makes those retries fail in the OS,
            # without waiting for Python to serve a 404 during Qt teardown.
            server.server_close()
            threading.Thread(target=server.shutdown, daemon=True, name='moviebox-media-retire').start()
        for client in clients:
            try: client.shutdown(socket.SHUT_RDWR)
            except OSError: pass

    def close(self):
        self.cancel_active()
