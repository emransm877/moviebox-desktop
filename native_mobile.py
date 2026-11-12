"""Minimal native-protocol diagnostic, based on this APK's recovered signer.

Uses truthful desktop metadata. Never generates stock-certificate/build attestation,
never imports phone sessions, and never changes account access flags.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import re
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HOST = 'https://api6.aoneroom.com'
PREFIX = '/wefeed-mobile-bff'


def load_public_protocol_key():
    # Shared public API protocol metadata from the supplied APK manifest.
    value = '76iRl07s0xSN9jqmEWAt79EBJZulIQIsV64FZr2O'
    return base64.b64decode(value + "=" * (-len(value) % 4))


def signature(method, url, body, timestamp, key):
    parsed = urlsplit(url)
    pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query = '&'.join(f'{k}={pairs[k]}' for k in sorted(pairs))
    path = parsed.path + ('?' + query if query else '')
    text = '\n'.join([method.upper(), 'application/json', 'application/json',
        str(len(body)) if body is not None else '', str(timestamp),
        hashlib.md5(body[:102400]).hexdigest() if body is not None else '', path])
    digest = base64.b64encode(hmac.new(key, text.encode(), hashlib.md5).digest()).decode()
    return f'{timestamp}|2|{digest}'


class NativeMovieBox:
    def __init__(self, host=HOST):
        self.host = host
        self.token = ''
        self.key = load_public_protocol_key()
        self.device_id = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()
        self.gaid = uuid.uuid4().hex[:16]
        self.user_agent = 'com.community.oneroom/50020104 (Linux; U; Android 17; en_US; DesktopPort; Build/LOCAL; Cronet/135.0.7012.3) MovieBoxDesktop/0.1'
        # Recovered fixed protocol fields from the user's APK; local executable
        # identifies itself separately and does not claim hardware attestation.
        info = {'package_name': 'com.community.oneroom', 'version_name': '4.0.03.0930.03',
            'version_code': 50020104, 'os': 'android', 'os_version': '17',
            'device_id': self.device_id, 'gaid': self.gaid, 'install_ch': 'google-play',
            'install_store': 'gp', 'brand': 'Generic', 'model': 'DesktopPort',
            'system_language': 'en', 'net': 'NETWORK_WIFI', 'region': 'US',
            'timezone': 'Asia/Dhaka', 'sp_code': '20801', 'X-Child-UID': '',
            'X-Play-Mode': '2', 'X-Idle-Data': '1', 'X-Family-Mode': '0', 'X-Content-Mode': '0'}
        self.client_info = json.dumps(info, separators=(',', ':'))
        self.extra_headers = {'X-Child-UID': '', 'X-Play-Mode': '2', 'X-Idle-Data': '1',
                              'X-Family-Mode': '0', 'X-Content-Mode': '0'}
        self.last_play_info = {}
        self.caption_cache = {}
        self.caption_cache_times = {}
        self.resource_context = {}
        self.bootstrapped = False
        self.lock = threading.RLock()
        self.season_cache = {}
        self.max_resolution = 2160

    def request(self, path, params=None, body=None):
        url = self.host + PREFIX + path
        if params:
            url += '?' + urlencode(params)
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode() if body is not None else None
        method = 'POST' if data is not None else 'GET'
        ts = int(time.time() * 1000)
        headers = {'User-Agent': self.user_agent,
            'Accept': 'application/json', 'Content-Type': 'application/json',
            'X-Client-Token': f'{ts},{hashlib.md5(str(ts)[::-1].encode()).hexdigest()}',
            'x-tr-signature': signature(method, url, data, ts, self.key),
            'X-Client-Info': self.client_info, 'X-Client-Status': '0'}
        headers.update(self.extra_headers)
        with self.lock:
            token = self.token
        if token:
            headers['Authorization'] = 'Bearer ' + token
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=15) as response:
                user = response.headers.get('x-user')
                if user:
                    with self.lock:
                        self.token = json.loads(user).get('token', self.token)
                result = json.load(response)
        except HTTPError as error:
            try:
                message = json.loads(error.read(5000)).get('message') or error.reason
            except Exception:
                message = error.reason
            raise RuntimeError(f'Native API HTTP {error.code}: {message}') from None
        if result.get('code') not in (0, '0', None):
            raise RuntimeError('Native API: ' + str(result.get('message', result.get('code'))))
        return result.get('data', result)

    def home(self):
        return self.request('/tab-operating', {'page': 1, 'tabId': 0, 'version': ''})

    def warm_up(self):
        """Mint the normal guest token once; may run during the home-screen load."""
        with self.lock:
            if not self.token:
                self.home()
            self.bootstrapped = True

    def season_info(self, subject_id, *, refresh=False):
        key = str(subject_id)
        with self.lock:
            cached = self.season_cache.get(key)
        if not refresh and cached and time.monotonic() - cached[0] < 300:
            return cached[1]
        self.warm_up()
        result = self.request('/subject-api/season-info', {'host': self.host, 'subjectId': key})
        with self.lock:
            self.season_cache[key] = (time.monotonic(), result)
        return result

    def play_info(self, subject_id, season=0, episode=0):
        return self.request('/subject-api/play-info', {'subjectId': subject_id, 'se': season,
            'ep': episode, 'host': self.host})

    def resources(self, subject_id, season=0, episode=0, resolution=1080, *,
                  page=1, pager_mode=0, position=1, per_page=20):
        return self.request('/subject-api/resource', {'host': self.host, 'subjectId': subject_id,
            'page': page, 'perPage': per_page, 'all': 0, 'startPosition': position, 'endPosition': position,
            'pagerMode': pager_mode, 'resolution': resolution, 'se': season, 'epFrom': episode,
            'epTo': episode})

    @staticmethod
    def is_placeholder(stream):
        duration = int(stream.get('duration') or 0)
        size = int(stream.get('size') or 0)
        return (stream.get('format', '').upper() == 'MP4' and 0 < duration <= 30
                and 0 < size < 3 * 1024 * 1024)

    def apply_profile(self, profile):
        """Import only a sanitized compatibility profile, never phone identity/auth."""
        info = dict(profile.get('client_info') or {})
        for name in ['device_id', 'gaid', 'install_id', 'install_share_uid', 'session_id']:
            info.pop(name, None)
        info['device_id'] = self.device_id
        info['gaid'] = self.gaid
        info['sp_code'] = '20801'  # Literal constant in this APK's tg.b.o().
        self.client_info = json.dumps(info, separators=(',', ':'))
        self.extra_headers = {str(k): str(v) for k, v in (profile.get('extra_headers') or {}).items()
                              if not any(word in k.lower() for word in ['authorization', 'cookie', 'token', 'secret', 'signature'])}

    @staticmethod
    def _number(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def playback(self, subject, season=0, episode=0):
        """Resolve real source variants, not the first item in a mixed list.

        Native pagerMode=2 is the season/episode range selector. Mode 0 is
        ordinary pagination and silently ignores that range, hiding late episodes.
        Movies return a mixed-resolution list with no collectionResolutions.
        """
        self.warm_up()
        subject_id = str(subject['subjectId'])
        kind = self._number(subject.get('subjectType'))
        season, episode = self._number(season), self._number(episode)
        if kind == 1:
            season = episode = 0
        elif kind == 2 and (season <= 0 or episode <= 0):
            raise RuntimeError('Choose a season and episode before playing this series.')
        elif season <= 0 or episode <= 0:
            season = episode = 0
        mode = 2 if season > 0 else 0

        def fetch(resolution):
            return self.resources(subject_id, season, episode, resolution, pager_mode=mode)

        # A guest token is already warm after detail loading. No DASH request or
        # network probe is required before the actual MP4 resources request.
        first = fetch(1080)
        collection = first.get('collectionResolutions') or []
        allowed, locked = set(), set()
        for record in collection:
            resolution = self._number(record.get('resolution'))
            if not 0 < resolution <= self.max_resolution:
                continue
            if self._number(record.get('requireMemberType')):
                locked.add(resolution)
            else:
                allowed.add(resolution)

        result_by_quality = {}

        def collect(batch):
            for item in batch.get('list') or []:
                if season and (self._number(item.get('se')) != season or
                               self._number(item.get('ep')) != episode):
                    continue
                if self._number(item.get('requireMemberType')) or item.get('vipLocked'):
                    continue
                if not item.get('resourceLink'):
                    continue
                # Never infer a source's resolution from the requested quality:
                # a movie request for 1080 can return 480 followed by 1080.
                actual = self._number(item.get('resolution')) or self._number(batch.get('resolution'))
                if not 0 < actual <= self.max_resolution or actual in locked:
                    continue
                size, duration = self._number(item.get('size')), self._number(item.get('duration'))
                if self.is_placeholder({'format': 'MP4', 'size': size, 'duration': duration}):
                    continue
                if duration > 60 and 0 < size < 3 * 1024 * 1024:
                    continue
                stream_id = str(item.get('resourceId') or '')
                headers = {'User-Agent': self.user_agent}
                stream = {'url': item['resourceLink'], 'resolutions': actual,
                    'size': size, 'duration': duration, 'id': stream_id,
                    'headers': headers, 'codecName': item.get('codecName') or '',
                    'season': self._number(item.get('se')), 'episode': self._number(item.get('ep'))}
                previous = result_by_quality.get(actual)
                if previous is None or size > previous['size']:
                    result_by_quality[actual] = stream
                with self.lock:
                    self.caption_cache[(subject_id, stream_id)] = item.get('extCaptions') or []
                    self.caption_cache_times[(subject_id, stream_id)] = time.monotonic()
                    self.resource_context[(subject_id, stream_id)] = {
                        'season': self._number(item.get('se')),
                        'episode': self._number(item.get('ep')),
                        'duration': duration,
                        'resource_episode': self._number(item.get('episode'), episode)}

        collect(first)
        remaining = allowed - result_by_quality.keys() - {1080}
        failures = []
        if remaining:
            with ThreadPoolExecutor(max_workers=min(4, len(remaining)), thread_name_prefix='moviebox-quality') as workers:
                pending = {workers.submit(fetch, resolution): resolution for resolution in remaining}
                for future in as_completed(pending):
                    try:
                        collect(future.result())
                    except Exception as error:
                        failures.append(str(error))
        if not result_by_quality:
            if failures:
                raise RuntimeError(failures[0])
            raise RuntimeError('No unlocked native MP4 stream is available for this selection.')
        streams = sorted(result_by_quality.values(), key=lambda s: s['resolutions'], reverse=True)
        with self.lock:
            self.last_play_info = {'streams': streams, 'source': 'native-mp4',
                'subjectId': subject_id, 'season': season, 'episode': episode,
                'availableResolutions': [s['resolutions'] for s in streams]}
        return streams

    def captions(self, subject, stream_id, *, season=None, episode=None, refresh=False,
                 _variant_fallback=True):
        """Discover subtitles for this exact MP4 resource or streaming ID.

        Android uses get-ext-captions(resourceId, episode) for downloaded/MP4
        resources. Passing that resourceId as a DASH streamId can return a
        successful but empty response even when many external tracks exist.
        Never borrow a different episode's captions or cache an empty lookup.
        """
        key = (str(subject['subjectId']), str(stream_id))
        with self.lock:
            cached = self.caption_cache.get(key)
            age = time.monotonic() - self.caption_cache_times.get(key, 0)
            context = dict(self.resource_context.get(key) or {})
        if season is not None and context and self._number(season) != context['season']:
            raise ValueError('Subtitle resource does not match the selected season.')
        if episode is not None and context and self._number(episode) != context['episode']:
            raise ValueError('Subtitle resource does not match the selected episode.')
        if cached and not refresh and age < 240:
            return {'captions': cached}
        resource_episode = context.get('resource_episode', self._number(episode))

        def tracks(result):
            if isinstance(result, list):
                return result
            return (result.get('captions') or result.get('extCaptions') or
                    result.get('list') or result.get('items') or [])

        errors = []
        succeeded = False
        for path, parameters in [
            ('/subject-api/get-ext-captions', {'resourceId': str(stream_id), 'episode': resource_episode}),
            ('/subject-api/get-stream-captions', {'streamId': str(stream_id)}),
        ]:
            try:
                result = self.request(path, {'host': self.host, 'subjectId': key[0], **parameters})
                succeeded = True
                captions = tracks(result)
                if captions:
                    with self.lock:
                        self.caption_cache[key] = captions
                        self.caption_cache_times[key] = time.monotonic()
                    return {'captions': captions}
            except Exception as error:
                errors.append(error)
        # A quality variant can have no caption association while another MP4
        # of the same episode does. Only reuse descriptors when the exact
        # subject/season/episode and measured runtime agree (within two seconds).
        # The fallback never crosses titles, episodes or substantially different edits.
        if _variant_fallback and context.get('duration', 0) > 0:
            with self.lock:
                peers = [peer for peer, metadata in self.resource_context.items()
                         if peer[0] == key[0] and peer != key
                         and metadata['season'] == context['season']
                         and metadata['episode'] == context['episode']
                         and abs(metadata.get('duration', 0) - context['duration']) <= 2]
            for peer in peers[:3]:
                try:
                    result = self.captions(subject, peer[1], refresh=refresh, _variant_fallback=False)
                    if result['captions']:
                        return {**result, 'captionSourceResourceId': peer[1]}
                except Exception as error:
                    errors.append(error)
        if errors and not succeeded:
            raise errors[0]
        return {'captions': []}


if __name__ == '__main__':
    client = NativeMovieBox()
    output = {}
    for name, call in [('home', client.home),
                       ('play', lambda: client.play_info('6853990427147001176', 1, 1)),
                       ('resource', lambda: client.resources('6853990427147001176', 1, 1))]:
        try:
            result = call()
            output[name] = result
            print(name, 'OK', list(result) if isinstance(result, dict) else type(result).__name__)
        except Exception as error:
            output[name] = {'error': str(error)}
            print(name, str(error))
    Path(__file__).with_name('native-diagnostic-response.json').write_text(json.dumps(output), encoding='utf-8')
