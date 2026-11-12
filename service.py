"""Desktop service adapter recovered from MovieBox's public web client.

No Android runtime, embedded website, credential extraction, or access overrides.
"""
from __future__ import annotations
import hashlib
import json
import threading
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

API = 'https://h5-api.aoneroom.com/wefeed-h5api-bff'
SITE = 'https://movieboxhd.net'


class ServiceError(RuntimeError):
    pass


class MovieBoxService:
    def __init__(self, use_native=True):
        self.token = ''
        self.account_token = ''
        self.player_origin = ''
        self.player_referer = ''
        self.last_play_info = {}
        self.lock = threading.Lock()
        self.native = None
        if use_native:
            from native_mobile import NativeMovieBox
            self.native = NativeMovieBox()

    def request(self, path, body=None, *, origin=None):
        timestamp = str(int(time.time()))
        headers = {
            'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
            'Content-Type': 'application/json', 'Referer': SITE + '/',
            'X-Request-Lang': 'en',
            'X-Client-Info': json.dumps({'timezone': 'Asia/Dhaka'}),
            'X-Vip-Restrict': '1',
        }
        with self.lock:
            token = self.token
        if origin:
            headers['Referer'] = self.player_referer or origin.rstrip('/') + '/'
            if self.account_token:
                headers['Authorization'] = 'Bearer ' + self.account_token
        elif self.account_token or token:
            headers['Authorization'] = 'Bearer ' + (self.account_token or token)
        else:
            headers['X-Client-Token'] = timestamp + ',' + hashlib.md5(timestamp[::-1].encode()).hexdigest()
        url = (origin.rstrip('/') + '/wefeed-h5api-bff' if origin else API) + path
        req = Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urlopen(req, timeout=20) as response:
            user = response.headers.get('x-user')
            if user:
                with self.lock:
                    self.token = json.loads(user).get('token', self.token)
            data = json.load(response)
        if data.get('code') != 0:
            raise ServiceError(data.get('message') or 'MovieBox could not complete this request.')
        return data.get('data')

    def home(self):
        return self.request('/home?' + urlencode({'host': 'movieboxhd.net'}))

    def search(self, keyword, page=1):
        if not self.token:
            self.home()
        return self.request('/subject/search', {'keyword': keyword, 'page': page, 'perPage': 30, 'subjectType': 0})

    def suggest(self, keyword):
        if not self.token:
            self.home()
        response = self.request('/subject/search-suggest', {'keyword': keyword, 'perPage': 10})
        return response.get('items') or []

    def detail(self, subject):
        data = self.request('/detail?' + urlencode({'subjectId': subject['subjectId']}))
        item = data.get('subject') or subject
        try:
            kind = int(item.get('subjectType') or subject.get('subjectType') or 0)
        except (TypeError, ValueError):
            kind = 0
        item['subjectType'] = kind
        data['subject'] = item
        data['isSeries'] = kind == 2
        resource = data.get('resource') or {}
        data['resource'] = resource
        if kind == 1:
            # The API uses se=0 as a movie storage bucket, not a TV season.
            resource['seasons'] = []
            data['episodeMetadata'] = {}
            data['episode_count'] = 0
            return data
        if kind == 2 and self.native:
            try:
                native = self.native.season_info(item['subjectId'])
                if isinstance(native.get('seasons'), list):
                    resource['seasons'] = native['seasons']
                data['nativeMetadataAvailable'] = True
            except Exception:
                # Web details remain usable during a temporary native API outage.
                data['nativeMetadataAvailable'] = False
        episodes = {}
        normalised = []
        for record in resource.get('seasons') or []:
            try:
                number = int(record.get('se') or 0)
                maximum = max(0, min(10000, int(record.get('maxEp') or 0)))
            except (TypeError, ValueError):
                continue
            explicit = str(record.get('allEp') or '')
            available = sorted({int(ep.strip()) for ep in explicit.split(',') if ep.strip().isdigit()}) if explicit else list(range(1, maximum + 1))
            if not available:
                continue
            season = dict(record)
            season['se'] = number
            season['maxEp'] = max(available)
            season['episodeNumbers'] = available
            normalised.append(season)
            episodes[str(number)] = available
        resource['seasons'] = sorted(normalised, key=lambda season: season['se'])
        data['episodeMetadata'] = episodes
        data['episode_count'] = sum(len(values) for values in episodes.values())
        return data

    def playback(self, subject, season=0, episode=0):
        if self.native:
            try:
                streams = self.native.playback(subject, season, episode)
            except RuntimeError as error:
                raise ServiceError(str(error)) from None
            self.last_play_info = self.native.last_play_info
            return streams
        return self.web_playback(subject, season, episode)

    def web_playback(self, subject, season=0, episode=0):
        if not self.player_origin:
            advertised = self.request('/media-player/get-domain')
            parsed = urlparse(advertised)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ServiceError('MovieBox returned an invalid player address.')
            self.player_origin = f'https://{parsed.netloc}'
        params = {'subjectId': subject['subjectId'], 'se': season, 'ep': episode,
                  'detailPath': subject['detailPath'], 'streamSignType': 1, 'supportCodecs[h264]': 1}
        self.player_referer = self.player_origin + '/spa/videoPlayPage/movies/' + subject['detailPath'] + '?' + urlencode({'id': subject['subjectId']})
        data = self.request('/subject/play?' + urlencode(params), origin=self.player_origin)
        self.last_play_info = data
        if data.get('limited'):
            raise ServiceError('MovieBox has limited this playback. Open the service to review your access.')
        if data.get('hasResource') is False:
            raise ServiceError('MovieBox currently has no playable video for this selection.')
        max_resolution = (data.get('playConfig') or {}).get('maxResolution') or 99999
        streams = []
        for stream in data.get('streams') or []:
            try:
                resolution = int(stream.get('resolutions') or 0)
            except ValueError:
                resolution = 0
            if (stream.get('url') and not stream.get('vipLocked') and
                    not stream.get('vip_locked') and resolution <= int(max_resolution)):
                streams.append(stream)
        if not streams:
            raise ServiceError('No unlocked MP4 stream is available. This title may require a MovieBox account or membership.')
        return sorted(streams, key=lambda item: int(item.get('resolutions') or 0), reverse=True)

    def captions(self, subject, stream_id, *, season=None, episode=None, refresh=False):
        if self.native:
            return self.native.captions(subject, stream_id, season=season, episode=episode, refresh=refresh)
        return self.request('/subject/caption?' + urlencode({'format': 'MP4', 'id': stream_id,
            'subjectId': subject['subjectId'], 'detailPath': subject['detailPath']}), origin=self.player_origin)
