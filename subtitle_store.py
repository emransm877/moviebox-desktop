"""Download subtitles once per title/episode/language and replay locally."""
from dataclasses import asdict
import hashlib
import gzip
import io
import json
from pathlib import Path
import threading
import uuid
import zipfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from playback import Cue, parse_subtitles


class SubtitleStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, key, language):
        digest = hashlib.sha256((key + ':' + language).encode()).hexdigest()
        return self.directory / (digest + '.json')

    def _write(self, path, value):
        temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)

    def load(self, key, language):
        try:
            value = json.loads(self.path(key, language).read_text(encoding='utf-8'))
            cues = [Cue(int(c['start']), int(c['end']), str(c['text'])) for c in value['cues']]
            return {'cues': cues, 'language': value['language'], 'caption': value['caption']}
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save_text(self, key, language, caption, text):
        cues = parse_subtitles(text)
        if not cues:
            raise ValueError('The subtitle file has no readable timed captions.')
        path = self.path(key, language)
        # Retain the downloaded subtitle itself as well as a fast parsed index.
        path.with_suffix('.srt').write_text(text, encoding='utf-8')
        safe_caption = {name: caption[name] for name in ('id', 'lan', 'lanName') if name in caption}
        safe_caption['lan'] = language
        safe_caption.setdefault('lanName', language)
        self._write(path, {'language': language, 'caption': safe_caption,
                           'cues': [asdict(cue) for cue in cues]})
        return {'cues': cues, 'language': language, 'caption': safe_caption}

    def descriptors(self, key):
        try:
            return json.loads(self.path(key, '_languages').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []

    @staticmethod
    def decode_payload(data, charset=None):
        """Handle actual subtitle downloads without extracting archive paths."""
        limit = 4 * 1024 * 1024
        if data.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                data = compressed.read(limit + 1)
        if data.startswith(b'PK\x03\x04'):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                candidates = [entry for entry in archive.infolist()
                              if entry.filename.lower().endswith(('.srt', '.vtt')) and not entry.is_dir()]
                if not candidates:
                    raise ValueError('The download contains no SRT or WebVTT subtitles.')
                entry = candidates[0]
                if entry.file_size > limit:
                    raise ValueError('Subtitle download is too large.')
                data = archive.read(entry)
        if len(data) > limit:
            raise ValueError('Subtitle download is too large.')
        if data.startswith((b'\xff\xfe', b'\xfe\xff')):
            return data.decode('utf-16')
        try:
            return data.decode(charset or 'utf-8-sig')
        except (LookupError, UnicodeError):
            return data.decode('utf-8-sig', errors='replace')

    def prepare(self, key, language, discover):
        with self.lock:
            cached = self.load(key, language)
            if cached:
                descriptions = self.descriptors(key)
                if not any(c.get('lan') == language for c in descriptions):
                    descriptions.append(cached['caption'])
                return {**cached, 'captions': descriptions, 'cached': True}
        response = discover()
        captions = response.get('captions') or []
        descriptors = [{k: c[k] for k in ('id', 'lan', 'lanName') if k in c} for c in captions]
        self._write(self.path(key, '_languages'), descriptors)
        preferred = [c for c in captions if c.get('lan') == language and c.get('url')]
        preferred += [c for c in captions if c.get('lan') == 'en' and c.get('url') and c not in preferred]
        if not preferred:
            preferred = [c for c in captions if c.get('url')][:1]
        if not preferred:
            return {'captions': descriptors, 'cues': [], 'language': '', 'cached': False}
        errors = []
        for selected in preferred:
            actual_language = selected.get('lan') or language
            with self.lock:
                cached = self.load(key, actual_language)
            if cached:
                return {**cached, 'captions': descriptors, 'cached': True}
            try:
                with urlopen(Request(selected['url'], headers=selected.get('headers') or {'User-Agent': 'Mozilla/5.0'}), timeout=10) as response:
                    data = response.read(4 * 1024 * 1024 + 1)
                    headers = getattr(response, 'headers', None)
                    charset = headers.get_content_charset() if headers and hasattr(headers, 'get_content_charset') else None
                    text = self.decode_payload(data, charset)
                with self.lock:
                    cached = self.save_text(key, actual_language, selected, text)
                return {**cached, 'captions': descriptors, 'cached': False}
            except (OSError, ValueError, zipfile.BadZipFile, EOFError) as error:
                # A failed default download must not hide every other language.
                errors.append('HTTP ' + str(error.code) if isinstance(error, HTTPError) else type(error).__name__)
        return {'captions': descriptors, 'cues': [], 'language': '', 'cached': False,
                'error': 'Subtitle download failed (' + ', '.join(errors) + '). Choose a language to retry.'}
