"""Exact-resource subtitle discovery regressions; no live network required."""
import time
import unittest
from unittest.mock import Mock

from native_mobile import NativeMovieBox
from test_native_regressions import ready_native, source


class NativeCaptionRegressions(unittest.TestCase):
    def prepare(self):
        native = ready_native()
        resource = source(1080, season=8, episode=6)
        resource['episode'] = 806
        native.resources = Mock(return_value={'list': [resource]})
        stream = native.playback({'subjectId': 'got', 'subjectType': 2}, 8, 6)[0]
        return native, stream['id']

    def test_mp4_uses_external_caption_endpoint_and_encoded_episode(self):
        native, resource_id = self.prepare()
        track = {'id': 'english', 'lan': 'en', 'url': 'https://example.test/en.srt'}
        native.request = Mock(return_value={'extCaptions': [track]})
        self.assertEqual(native.captions({'subjectId': 'got'}, resource_id)['captions'], [track])
        path, params = native.request.call_args.args
        self.assertEqual(path, '/subject-api/get-ext-captions')
        self.assertEqual((params['resourceId'], params['episode']), (resource_id, 806))
        self.assertEqual(native.request.call_count, 1)

    def test_empty_external_result_falls_back_to_stream_endpoint(self):
        native = NativeMovieBox()
        native.request = Mock(side_effect=[{'extCaptions': []}, {'captions': [{'id': 'stream-en'}]}])
        self.assertEqual(len(native.captions({'subjectId': 'got'}, 'dash')['captions']), 1)
        self.assertEqual(native.request.call_args.args[0], '/subject-api/get-stream-captions')

    def test_empty_results_are_not_negatively_cached(self):
        native = NativeMovieBox()
        native.request = Mock(return_value={'extCaptions': []})
        for _ in range(2):
            self.assertEqual(native.captions({'subjectId': 'got'}, 'resource')['captions'], [])
        self.assertEqual(native.request.call_count, 4)

    def test_stale_signed_caption_descriptor_is_refreshed(self):
        native = NativeMovieBox()
        key = ('got', 'resource')
        native.caption_cache[key] = [{'id': 'old'}]
        native.caption_cache_times[key] = time.monotonic() - 241
        native.request = Mock(return_value={'extCaptions': [{'id': 'new'}]})
        self.assertEqual(native.captions({'subjectId': 'got'}, 'resource')['captions'][0]['id'], 'new')

    def test_wrong_episode_cannot_reuse_even_positive_cached_tracks(self):
        native, resource_id = self.prepare()
        key = ('got', resource_id)
        native.caption_cache[key] = [{'id': 's8e6'}]
        native.caption_cache_times[key] = time.monotonic()
        with self.assertRaisesRegex(ValueError, 'episode'):
            native.captions({'subjectId': 'got'}, resource_id, season=8, episode=5)

    def test_external_failure_does_not_hide_working_stream_tracks(self):
        native = NativeMovieBox()
        native.request = Mock(side_effect=[RuntimeError('temporary'), {'extCaptions': [{'id': 'en'}]}])
        self.assertEqual(native.captions({'subjectId': 'got'}, 'id')['captions'][0]['id'], 'en')

    def test_both_failures_are_retryable_errors(self):
        native = NativeMovieBox()
        native.request = Mock(side_effect=RuntimeError('temporary'))
        with self.assertRaisesRegex(RuntimeError, 'temporary'):
            native.captions({'subjectId': 'got'}, 'id')

    def test_quality_fallback_requires_same_episode_and_matching_runtime(self):
        native, resource_id = self.prepare()
        native.resource_context[('got', 'wrong-episode')] = {
            'season': 8, 'episode': 5, 'duration': 2400, 'resource_episode': 805}
        native.resource_context[('got', 'different-edit')] = {
            'season': 8, 'episode': 6, 'duration': 2200, 'resource_episode': 806}
        native.resource_context[('got', '720p')] = {
            'season': 8, 'episode': 6, 'duration': 2400, 'resource_episode': 806}
        def request(path, params):
            if params.get('resourceId') == '720p':
                return {'extCaptions': [{'id': 'same-episode-en'}]}
            return {'extCaptions': []}
        native.request = Mock(side_effect=request)
        result = native.captions({'subjectId': 'got'}, resource_id)
        self.assertEqual(result['captionSourceResourceId'], '720p')
        self.assertEqual(result['captions'][0]['id'], 'same-episode-en')
        self.assertEqual(native.request.call_count, 3)


if __name__ == '__main__':
    unittest.main()
