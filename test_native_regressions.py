"""Regression coverage for mixed movie quality lists and late TV episodes."""
import unittest
from unittest.mock import Mock

from native_mobile import NativeMovieBox
from service import MovieBoxService


def source(resolution, *, season=0, episode=0, member=0, size=500_000_000):
    return {'resolution': resolution, 'resourceLink': f'https://example.test/{season}-{episode}-{resolution}.mp4',
            'resourceId': f'{season}-{episode}-{resolution}', 'duration': 2400,
            'size': size, 'requireMemberType': member, 'se': season, 'ep': episode,
            'codecName': 'h264', 'extCaptions': []}


def ready_native():
    native = NativeMovieBox()
    native.token = 'test-local-guest'
    native.home = Mock(side_effect=AssertionError('Existing guest must not bootstrap again'))
    native.play_info = Mock(side_effect=AssertionError('MP4 resolution must not wait for a DASH request'))
    return native


class NativeQualityRegressions(unittest.TestCase):
    def test_movie_mixed_list_keeps_1080_after_480(self):
        native = ready_native()
        native.resources = Mock(return_value={'resolution': 0, 'collectionResolutions': [],
            'list': [source(480), source(1080)]})
        streams = native.playback({'subjectId': 'odyssey', 'subjectType': 1})
        self.assertEqual([stream['resolutions'] for stream in streams], [1080, 480])
        self.assertEqual(native.resources.call_count, 1)
        self.assertEqual(native.resources.call_args.kwargs['pager_mode'], 0)
        self.assertEqual(streams[0]['id'], '0-0-1080')

    def test_episode_65_uses_exact_episode_range_mode(self):
        native = ready_native()
        def resources(sid, season, episode, resolution, **kwargs):
            selected_episode = episode if kwargs.get('pager_mode') == 2 else 1
            return {'collectionResolutions': [], 'list': [source(1080, season=season, episode=selected_episode)]}
        native.resources = Mock(side_effect=resources)
        streams = native.playback({'subjectId': 'khush', 'subjectType': 2}, 1, 65)
        self.assertEqual(streams[0]['episode'], 65)
        self.assertEqual(native.resources.call_args.kwargs['pager_mode'], 2)

    def test_season_two_does_not_reuse_global_position_eight(self):
        native = ready_native()
        def resources(sid, season, episode, resolution, **kwargs):
            return {'list': [source(1080, season=2 if kwargs.get('pager_mode') == 2 else 1, episode=8)]}
        native.resources = Mock(side_effect=resources)
        streams = native.playback({'subjectId': 'rings', 'subjectType': 2}, 2, 8)
        self.assertEqual((streams[0]['season'], streams[0]['episode']), (2, 8))

    def test_unlocked_real_4k_is_not_silently_capped_at_1080(self):
        native = ready_native()
        native.resources = Mock(side_effect=lambda sid, se, ep, res, **kw: {
            'collectionResolutions': [{'resolution': 1080, 'requireMemberType': 0},
                                     {'resolution': 2160, 'requireMemberType': 0}],
            'list': [source(res)]})
        streams = native.playback({'subjectId': 'film', 'subjectType': 1})
        self.assertEqual([stream['resolutions'] for stream in streams], [2160, 1080])

    def test_member_required_quality_is_never_requested_or_exposed(self):
        native = ready_native()
        native.resources = Mock(return_value={'collectionResolutions': [
            {'resolution': 1080, 'requireMemberType': 0},
            {'resolution': 2160, 'requireMemberType': 1}],
            'list': [source(1080), source(2160, member=1)]})
        streams = native.playback({'subjectId': 'film', 'subjectType': 1})
        self.assertEqual([stream['resolutions'] for stream in streams], [1080])
        self.assertEqual(native.resources.call_count, 1)

    def test_requested_quality_never_relabels_actual_lower_source(self):
        native = ready_native()
        native.resources = Mock(return_value={'resolution': 0, 'list': [source(480)]})
        streams = native.playback({'subjectId': 'film', 'subjectType': 1})
        self.assertEqual(streams[0]['resolutions'], 480)

    def test_failed_optional_variant_does_not_discard_playable_hd(self):
        native = ready_native()
        def resources(sid, season, episode, resolution, **kwargs):
            if resolution == 360:
                raise RuntimeError('Temporary low-quality source outage')
            return {'collectionResolutions': [{'resolution': 1080}, {'resolution': 360}],
                    'list': [source(1080)]}
        native.resources = Mock(side_effect=resources)
        streams = native.playback({'subjectId': 'film', 'subjectType': 1})
        self.assertEqual([stream['resolutions'] for stream in streams], [1080])

    def test_upgrade_clip_is_not_mislabeled_as_feature(self):
        native = ready_native()
        fake = source(1080, size=824720)
        fake['duration'] = 23
        native.resources = Mock(return_value={'list': [fake]})
        with self.assertRaisesRegex(RuntimeError, 'No unlocked native MP4'):
            native.playback({'subjectId': 'film', 'subjectType': 1})


class DetailRegressions(unittest.TestCase):
    def test_movie_storage_bucket_does_not_become_season_zero(self):
        service = MovieBoxService(use_native=False)
        service.native = Mock()
        service.request = Mock(return_value={'subject': {'subjectId': 'film', 'subjectType': 1},
            'resource': {'seasons': [{'se': 0, 'maxEp': 0}]}})
        result = service.detail({'subjectId': 'film'})
        self.assertFalse(result['isSeries'])
        self.assertEqual(result['resource']['seasons'], [])
        service.native.season_info.assert_not_called()

    def test_series_uses_native_explicit_episode_metadata(self):
        service = MovieBoxService(use_native=False)
        service.native = Mock()
        service.native.season_info.return_value = {'seasons': [{'se': '1', 'maxEp': 65, 'allEp': '1,3,65'}]}
        service.request = Mock(return_value={'subject': {'subjectId': 'series', 'subjectType': 2},
            'resource': {'seasons': [{'se': 1, 'maxEp': 20}]}})
        result = service.detail({'subjectId': 'series'})
        self.assertTrue(result['isSeries'])
        self.assertEqual(result['episodeMetadata'], {'1': [1, 3, 65]})
        self.assertEqual(result['resource']['seasons'][0]['episodeNumbers'], [1, 3, 65])


if __name__ == '__main__':
    unittest.main()
