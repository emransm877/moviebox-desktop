import gzip
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile
from subtitle_store import SubtitleStore

SRT = '\ufeff1\n00:00:01,000 --> 00:00:03,500\nA real timed caption.\n'


class SubtitleStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SubtitleStore(Path(self.temp.name))

    def test_failed_default_keeps_languages_and_retries_on_next_play(self):
        tracks = [{'id': 'one', 'lan': 'en', 'lanName': 'English', 'url': 'https://example.invalid/en.srt'},
                  {'id': 'two', 'lan': 'fr', 'lanName': 'French', 'url': 'https://example.invalid/fr.srt'}]
        discover = lambda: {'captions': tracks}
        failure = HTTPError(tracks[0]['url'], 503, 'Unavailable', {}, None)
        with patch('subtitle_store.urlopen', side_effect=failure):
            first = self.store.prepare('title:8:6', 'en', discover)
        self.assertEqual(len(first['captions']), 2)
        self.assertFalse(first['cues'])
        self.assertIn('error', first)
        self.assertEqual(len(self.store.descriptors('title:8:6')), 2)
        with patch('subtitle_store.urlopen', return_value=io.BytesIO(SRT.encode())):
            second = self.store.prepare('title:8:6', 'en', discover)
        self.assertEqual(second['cues'][0].text, 'A real timed caption.')
        with patch('subtitle_store.urlopen', side_effect=AssertionError('Network used for cached subtitles')):
            replay = self.store.prepare('title:8:6', 'en', lambda: self.fail('Discovery used for cached subtitles'))
        self.assertTrue(replay['cached'])
        self.assertIsNone(self.store.load('title:8:5', 'en'))

    def test_another_english_track_can_recover_an_expired_link(self):
        tracks = [{'id': str(n), 'lan': 'en', 'url': f'https://example.invalid/{n}.srt'} for n in range(2)]
        with patch('subtitle_store.urlopen', side_effect=[HTTPError(tracks[0]['url'], 403, 'Expired', {}, None), io.BytesIO(SRT.encode())]):
            result = self.store.prepare('title:1:1', 'en', lambda: {'captions': tracks})
        self.assertTrue(result['cues'])
        self.assertEqual(result['caption']['id'], '1')

    def test_gzip_zip_and_utf16_downloads_parse_without_extracting_paths(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('../nested/subtitle.srt', SRT)
        for data in [SRT.encode(), SRT.encode('utf-16'), gzip.compress(SRT.encode()), archive.getvalue()]:
            text = self.store.decode_payload(data)
            result = self.store.save_text('title:0:0', 'en', {'lanName': 'English'}, text)
            self.assertEqual(result['cues'][0].start, 1000)
        self.assertFalse((Path(self.temp.name).parent / 'nested').exists())


if __name__ == '__main__':
    unittest.main()
