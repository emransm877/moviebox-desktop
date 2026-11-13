import copy
import io
import json
import unittest
from unittest.mock import patch
from release_updates import (API_URL, CHECK_INTERVAL, MAX_METADATA_BYTES,
    check_due, check_for_update, fetch_latest, notice_is_allowed, parse_version,
    record_result, select_release, _NoRedirect)


def release(version='0.6.0'):
    tag = 'v' + version
    base = 'https://github.com/emransm877/moviebox-desktop/releases/'
    def asset(name):
        return {'name': name, 'state': 'uploaded', 'size': 42000000,
                'browser_download_url': base + 'download/' + tag + '/' + name}
    return {'tag_name': tag, 'draft': False, 'prerelease': False,
            'html_url': base + 'tag/' + tag,
            'assets': [asset(f'MovieBox-Desktop-{version}-windows-x64.zip'),
                       asset(f'MovieBox-Setup-{version}-windows-x64.exe')]}


class ReleaseUpdatesTests(unittest.TestCase):
    def test_prefers_real_setup_over_portable_zip(self):
        notice = select_release(release(), '0.5.0')
        self.assertEqual(notice.version, '0.6.0')
        self.assertTrue(notice.asset_name.endswith('.exe'))
        self.assertFalse(notice.portable)

    def test_portable_release_remains_available(self):
        data = release()
        data['assets'] = data['assets'][:1]
        self.assertTrue(select_release(data, '0.5.0').portable)

    def test_equal_older_skipped_versions_are_silent(self):
        for data, current, skip in [(release('0.5.0'), '0.5.0', ''),
                                     (release('0.4.0'), '0.5.0', ''),
                                     (release(), '0.5.0', 'v0.6.0')]:
            self.assertIsNone(select_release(data, current, skip))

    def test_malformed_and_prerelease_versions_are_rejected(self):
        for value in ('0.6', '0.6.0-beta', '0.6.0+build', ' 0.6.0', '00.6.0',
                      'v0.6.0/other', '9' * 200, None, 7):
            self.assertIsNone(parse_version(value))
        for field in ('draft', 'prerelease'):
            data = release(); data[field] = True
            self.assertIsNone(select_release(data, '0.5.0'))

    def test_no_missing_or_unuploaded_installer(self):
        for replacement in ([], 'not an array', [None], [{'name': 'MovieBox-Setup-0.6.0-windows-x64.exe', 'state': 'new'}]):
            data = release(); data['assets'] = replacement
            self.assertIsNone(select_release(data, '0.5.0'))

    def test_cross_repository_and_misleading_urls_are_rejected(self):
        for untrusted in (
            'http://github.com/emransm877/moviebox-desktop/releases/tag/v0.6.0',
            'https://github.com.attacker.test/emransm877/moviebox-desktop/releases/tag/v0.6.0',
            'https://github.com@attacker.test/emransm877/moviebox-desktop/releases/tag/v0.6.0',
            'https://github.com/emransm877/other/releases/tag/v0.6.0',
            'https://github.com/emransm877/moviebox-desktop/releases/tag/v0.6.0?redirect=elsewhere',
            'https://github.com:443/emransm877/moviebox-desktop/releases/tag/v0.6.0',
        ):
            data = release(); data['html_url'] = untrusted
            self.assertIsNone(select_release(data, '0.5.0'))
        data = release(); data['assets'] = [data['assets'][1]]
        data['assets'][0]['browser_download_url'] = 'https://github.com/attacker/app/releases/download/v0.6.0/MovieBox-Setup-0.6.0-windows-x64.exe'
        self.assertIsNone(select_release(data, '0.5.0'))

    def test_invalid_asset_sizes_rejected(self):
        for size in (0, -1, True, '123', 3 * 1024**3):
            data = release(); data['assets'] = [data['assets'][1]]
            data['assets'][0]['size'] = size
            self.assertIsNone(select_release(data, '0.5.0'))

    def test_daily_limit_optout_and_clock_rollback(self):
        now = CHECK_INTERVAL * 10
        self.assertTrue(check_due({}, now))
        self.assertFalse(check_due({'enabled': False}, now, force=True))
        self.assertFalse(check_due({'enabled': 'false'}, now))
        self.assertFalse(check_due({'last_checked': now - 10}, now))
        self.assertTrue(check_due({'last_checked': now - CHECK_INTERVAL}, now))
        self.assertTrue(check_due({'last_checked': now + 1000}, now))
        self.assertTrue(check_due({'last_checked': 'corrupt'}, now))
        self.assertTrue(check_due({'last_checked': now - 10}, now, force=True))

    def test_failed_request_records_attempt_and_remains_silent(self):
        def offline(_):
            raise OSError('Network unavailable')
        result = check_for_update('0.5.0', {}, now=100000, fetch=offline)
        self.assertTrue(result.attempted)
        self.assertIsNone(result.notice)
        self.assertEqual(result.error, 'Update check unavailable')
        updated = record_result({}, result)
        self.assertFalse(check_due(updated, 100001))

    def test_no_fetch_when_disabled_or_throttled(self):
        for settings in ({'enabled': False}, {'last_checked': 99999}):
            with patch('release_updates.fetch_latest') as fetch:
                self.assertFalse(check_for_update('0.5.0', settings, now=100000).attempted)
                fetch.assert_not_called()

    def test_worker_does_not_mutate_settings_and_preserves_late_choices(self):
        settings = {'enabled': True}
        before = copy.deepcopy(settings)
        result = check_for_update('0.5.0', settings, now=100000, fetch=lambda _: release())
        self.assertEqual(settings, before)
        settings.update(enabled=False, skipped_version='0.6.0')
        self.assertFalse(notice_is_allowed(settings, result.notice))
        self.assertFalse(record_result(settings, result)['enabled'])
        self.assertEqual(record_result(settings, result)['skipped_version'], '0.6.0')

    def test_public_metadata_request_is_bounded_and_uses_fixed_endpoint(self):
        class Response(io.BytesIO):
            status = 200
        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                return Response(json.dumps(release()).encode())
        opener = Opener()
        with patch('release_updates.build_opener', return_value=opener):
            self.assertEqual(fetch_latest('0.5.0')['tag_name'], 'v0.6.0')
        self.assertEqual(opener.request.full_url, API_URL)
        self.assertEqual(opener.timeout, 8)
        self.assertNotIn('Authorization', opener.request.headers)
        class HugeOpener:
            def open(self, request, timeout):
                return Response(b'x' * (MAX_METADATA_BYTES + 1))
        with patch('release_updates.build_opener', return_value=HugeOpener()):
            with self.assertRaises(ValueError):
                fetch_latest('0.5.0')

    def test_redirects_are_not_followed(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://attacker.test/'))


if __name__ == '__main__':
    unittest.main()
