from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import threading
import re
from urllib.request import Request, urlopen


@dataclass
class Download:
    url: str
    target: Path
    headers: dict
    received: int = 0
    total: int = 0
    status: str = 'Starting'
    cancelled: threading.Event = field(default_factory=threading.Event)

    def run(self):
        partial = self.target.with_suffix(self.target.suffix + '.part')
        try:
            self.target.parent.mkdir(parents=True, exist_ok=True)
            offset = partial.stat().st_size if partial.exists() else 0
            headers = dict(self.headers)
            if offset:
                headers['Range'] = f'bytes={offset}-'
            with urlopen(Request(self.url, headers=headers), timeout=20) as response:
                append = False
                if response.status == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if not match:
                        raise ValueError('Invalid partial download response')
                    start, end, total = map(int, match.groups())
                    if start != offset or end < start or end + 1 != total:
                        raise ValueError('Incomplete or mismatched download range')
                    length = response.headers.get('Content-Length')
                    if length and int(length) != end - start + 1:
                        raise ValueError('Download range length mismatch')
                    append = offset > 0
                elif response.status != 200:
                    raise ValueError('Unexpected download response')
                self.received = offset if append else 0
                self.total = self.received + int(response.headers.get('Content-Length') or 0)
                self.status = 'Downloading'
                with partial.open('ab' if append else 'wb') as output:
                    while not self.cancelled.is_set():
                        data = response.read(262144)
                        if not data:
                            break
                        output.write(data)
                        self.received += len(data)
                if self.cancelled.is_set():
                    self.status = 'Paused'
                elif self.total and self.received < self.total:
                    self.status = 'Interrupted'
                else:
                    partial.replace(self.target)
                    self.status = 'Complete'
        except Exception as error:
            self.status = 'Error: ' + str(error)
        return self
