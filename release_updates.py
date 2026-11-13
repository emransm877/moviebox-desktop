"""Optional, metadata-only GitHub release checks. Never downloads or installs apps."""
from dataclasses import dataclass
import json
import math
import re
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = 'emransm877/moviebox-desktop'
RELEASES_URL = 'https://github.com/' + REPOSITORY + '/releases'
API_URL = 'https://api.github.com/repos/' + REPOSITORY + '/releases/latest'
CHECK_INTERVAL = 24 * 60 * 60
MAX_METADATA_BYTES = 512 * 1024
MAX_ASSET_BYTES = 2 * 1024 * 1024 * 1024
_VERSION = re.compile(r'v?(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\Z')


@dataclass(frozen=True)
class UpdateNotice:
    version: str
    release_url: str
    download_url: str
    asset_name: str
    asset_size: int
    portable: bool = False


@dataclass(frozen=True)
class CheckResult:
    attempted: bool
    checked_at: float | None = None
    notice: UpdateNotice | None = None
    error: str = ''


def parse_version(value):
    """Only normal three-part stable versions; prerelease/build suffixes fail closed."""
    if not isinstance(value, str):
        return None
    match = _VERSION.fullmatch(value)
    return tuple(int(part) for part in match.groups()) if match else None


def _enabled(settings):
    return isinstance(settings, dict) and settings.get('enabled', True) is True


def check_due(settings, now=None, *, force=False):
    """Force bypasses the daily interval, never the user's disabled setting."""
    if not _enabled(settings):
        return False
    now = time.time() if now is None else float(now)
    try:
        previous = float(settings.get('last_checked') or 0)
    except (TypeError, ValueError):
        previous = 0
    if not math.isfinite(now) or now < 0:
        return False
    if not math.isfinite(previous) or previous < 0:
        previous = 0
    return bool(force or not previous or now - previous >= CHECK_INTERVAL or previous > now + 300)


def _trusted_url(value, expected_path):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parts = urlsplit(value)
        return (parts.scheme == 'https' and parts.netloc == 'github.com'
                and parts.path == expected_path and not parts.query and not parts.fragment)
    except ValueError:
        return False


def select_release(data, current_version, skipped_version=''):
    """Return a newer published release with an exact same-repository install asset."""
    current = parse_version(current_version)
    if not current or not isinstance(data, dict):
        return None
    if data.get('draft') is not False or data.get('prerelease') is not False:
        return None
    tag = data.get('tag_name')
    version = parse_version(tag)
    if not version or version <= current or parse_version(skipped_version) == version:
        return None
    canonical = '.'.join(map(str, version))
    release_path = '/' + REPOSITORY + '/releases/tag/' + tag
    if not _trusted_url(data.get('html_url'), release_path):
        return None
    assets = data.get('assets')
    if not isinstance(assets, list):
        return None
    names = [(f'MovieBox-Setup-{canonical}-windows-x64.exe', False),
             (f'MovieBox-Desktop-{canonical}-windows-x64.zip', True)]
    for expected_name, portable in names:
        for asset in assets:
            if not isinstance(asset, dict) or asset.get('name') != expected_name or asset.get('state') != 'uploaded':
                continue
            size = asset.get('size')
            if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_ASSET_BYTES:
                continue
            path = '/' + REPOSITORY + '/releases/download/' + tag + '/' + expected_name
            if _trusted_url(asset.get('browser_download_url'), path):
                return UpdateNotice(canonical, data['html_url'], asset['browser_download_url'], expected_name, size, portable)
    return None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def fetch_latest(current_version):
    """Read bounded public metadata over HTTPS; redirects are deliberately rejected."""
    request = Request(API_URL, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'MovieBoxDesktop/' + current_version + ' optional-update-check',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with build_opener(_NoRedirect()).open(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError('Release metadata unavailable')
        raw = response.read(MAX_METADATA_BYTES + 1)
        if len(raw) > MAX_METADATA_BYTES:
            raise ValueError('Release metadata exceeds limit')
        value = json.loads(raw.decode('utf-8'))
        if not isinstance(value, dict):
            raise ValueError('Invalid release metadata')
        return value


def check_for_update(current_version, settings, *, now=None, force=False, fetch=None):
    """Run in a worker, returning an immutable result without mutating UI state.

    Call record_result on the UI thread even after a failed request. This prevents
    offline/rate-limited clients from hammering GitHub on every timer tick.
    """
    now = time.time() if now is None else float(now)
    if not parse_version(current_version) or not check_due(settings, now, force=force):
        return CheckResult(False)
    try:
        data = (fetch or fetch_latest)(current_version)
        notice = select_release(data, current_version, settings.get('skipped_version', ''))
        return CheckResult(True, now, notice)
    except (OSError, ValueError, TypeError, UnicodeError):
        return CheckResult(True, now, error='Update check unavailable')


def record_result(settings, result):
    """Merge into current settings, retaining user choices made during the request."""
    updated = dict(settings)
    if result.attempted and result.checked_at is not None:
        updated['last_checked'] = result.checked_at
    return updated


def notice_is_allowed(settings, notice):
    """Recheck opt-out/skip when a queued notice is about to become visible."""
    return bool(notice and _enabled(settings)
                and parse_version(settings.get('skipped_version', '')) != parse_version(notice.version))
