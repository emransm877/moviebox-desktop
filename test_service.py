import unittest
from service import MovieBoxService, ServiceError
from playback import parse_subtitles, Subtitles, select_quality


class PlaybackAccessTests(unittest.TestCase):
    def service(self, data):
        api = MovieBoxService(use_native=False)
        api.player_origin = 'https://example.test'
        api.request = lambda *args, **kwargs: data
        return api

    def test_locked_and_over_resolution_streams_are_excluded(self):
        api = self.service({'hasResource': True, 'playConfig': {'maxResolution': 480}, 'streams': [
            {'url': 'https://example.test/free', 'resolutions': '480', 'vipLocked': False},
            {'url': 'https://example.test/locked', 'resolutions': '1080', 'vipLocked': True},
            {'url': 'https://example.test/too-high', 'resolutions': '720', 'vipLocked': False}]})
        self.assertEqual([s['resolutions'] for s in api.playback({'subjectId': '1', 'detailPath': 'sample'})], ['480'])

    def test_daily_limit_is_not_bypassed(self):
        with self.assertRaisesRegex(ServiceError, 'limited'):
            self.service({'limited': True}).playback({'subjectId': '1', 'detailPath': 'sample'})

    def test_unavailable_title_is_reported(self):
        with self.assertRaisesRegex(ServiceError, 'no playable video'):
            self.service({'hasResource': False}).playback({'subjectId': '1', 'detailPath': 'sample'})

    def test_subtitle_seek_and_end_boundary(self):
        cues = parse_subtitles('1\n00:00:01,000 --> 00:00:02,000\n<i>Hello</i>\n\n2\n00:00:04,000 --> 00:00:05,000\nWorld')
        track = Subtitles()
        track.set(cues)
        self.assertEqual(track.at(1500), 'Hello')
        self.assertEqual(track.at(2000), '')
        self.assertEqual(track.at(4500), 'World')
        self.assertEqual(track.at(1500), 'Hello')

    def test_auto_quality_reserves_bandwidth(self):
        streams = [{'resolutions': '480', 'size': '10000000', 'duration': 100},
                   {'resolutions': '1080', 'size': '60000000', 'duration': 100}]
        self.assertEqual(select_quality(streams, 2)['resolutions'], '480')
        self.assertEqual(select_quality(streams, 10)['resolutions'], '1080')


if __name__ == '__main__':
    unittest.main()
