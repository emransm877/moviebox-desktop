"""Subtitle timing and conservative quality selection, independent of the UI."""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass
import html
import re
import time
from urllib.request import Request, urlopen


@dataclass
class Cue:
    start: int
    end: int
    text: str


def millis(value):
    parts = value.replace(',', '.').split(':')
    if len(parts) == 2:
        parts.insert(0, '0')
    return round((int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])) * 1000)


def parse_subtitles(text):
    cues = []
    text = text.lstrip('\ufeff').replace('\r\n', '\n')
    for block in re.split(r'\n\s*\n', text):
        lines = block.strip().splitlines()
        for index, line in enumerate(lines):
            match = re.match(r'\s*([\d:.,]+)\s*-->\s*([\d:.,]+)', line)
            if match:
                try:
                    start, end = millis(match[1]), millis(match[2])
                except (ValueError, IndexError):
                    break
                caption = html.unescape(re.sub(r'<[^>]+>', '', '\n'.join(lines[index + 1:])))
                caption = re.sub(r'\{\\[^}]*\}', '', caption)
                if end > start and caption:
                    cues.append(Cue(start, end, caption))
                break
    return sorted(cues, key=lambda cue: cue.start)


class Subtitles:
    def __init__(self):
        self.cues, self.starts = [], []

    def set(self, cues):
        self.cues = sorted(cues, key=lambda cue: cue.start)
        self.starts = [cue.start for cue in self.cues]

    def at(self, position):
        index = bisect_right(self.starts, position) - 1
        if index >= 0 and position < self.cues[index].end:
            return self.cues[index].text
        return ''


def fetch_subtitles(url, headers=None):
    with urlopen(Request(url, headers=headers or {'User-Agent': 'Mozilla/5.0'}), timeout=15) as response:
        data = response.read(4 * 1024 * 1024)
    return parse_subtitles(data.decode('utf-8-sig', errors='replace'))


def measure_mbps(url, headers=None):
    started = time.monotonic()
    with urlopen(Request(url, headers={**({'User-Agent': 'Mozilla/5.0'} if not headers else headers), 'Range': 'bytes=0-1048575'}), timeout=8) as response:
        data = response.read(1048576)
    return len(data) * 8 / max(.05, time.monotonic() - started) / 1_000_000


def select_quality(streams, bandwidth_mbps):
    """Reserve 40% of measured capacity; only consider already authorized URLs."""
    ordered = sorted(streams, key=lambda stream: int(stream.get('resolutions') or 0))
    if not ordered:
        return None
    chosen = ordered[0]
    for stream in ordered:
        duration, size = float(stream.get('duration') or 0), float(stream.get('size') or 0)
        resolution = int(stream.get('resolutions') or 480)
        bitrate = size * 8 / duration / 1e6 if duration and size else {360: .8, 480: 1.5, 720: 3, 1080: 6, 2160: 20}.get(resolution, 6)
        if bitrate <= bandwidth_mbps * .6:
            chosen = stream
    return chosen
