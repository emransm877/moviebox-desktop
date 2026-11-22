"""UTF-8 boundaries and UI literals; never rewrite opaque or subtitle content."""
import copy
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from catalogue_cache import CatalogueCache
from library_store import LibraryStore
from native_mobile import NativeMovieBox
from service import MovieBoxService

ROOT = Path(__file__).resolve().parent
TITLE = 'বাংলা · 日本語 – العربية • Série “é” 😀'
SUBJECT = {'subjectId': 'opaque-\u00c3\u00a9-id', 'subjectType': 2, 'title': TITLE,
           'description': 'Ângela / Ãlvaro / São Paulo / Français / Русский / 한국어',
           'genre': 'Drama,Animation', 'countryName': 'Côte d’Ivoire',
           'cover': {'url': 'https://example.test/opaque-\u00c3\u00a9?q=\u00e2\u20ac\u2122'},
           'headers': {'X-Test': 'opaque-\u00c2\u00b7'},
           'token': 'opaque-\u00c3\u00a9', 'base64': 'w4PCqQ==',
           'captions': [{'lanName': 'বাংলা', 'text': 'literal cue \u00c2\u00b7 remains literal'}]}


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        # Deliberately misleading HTTP charset: JSON bytes remain authoritative.
        self.headers = {'Content-Type': 'application/json; charset=ISO-8859-1',
                        'x-user': json.dumps({'token': 'synthetic-opaque-\u00c3\u00a9'})}


class JsonEncodingTests(unittest.TestCase):
    def payload(self):
        return {'code': 0, 'data': {'subject': copy.deepcopy(SUBJECT)}}

    def test_web_json_utf8_ignores_misleading_latin1_charset_without_rewriting(self):
        api = MovieBoxService(use_native=False)
        expected = self.payload()['data']
        raw = json.dumps(self.payload(), ensure_ascii=False).encode('utf-8')
        with patch('service.urlopen', return_value=Response(raw)):
            result = api.request('/owned-fixture')
        self.assertEqual(result, expected)
        self.assertEqual(api.token, 'synthetic-opaque-\u00c3\u00a9')

    def test_native_json_utf8_preserves_titles_cues_and_opaque_fields(self):
        api = NativeMovieBox(host='https://example.test')
        expected = self.payload()['data']
        raw = json.dumps(self.payload(), ensure_ascii=False).encode('utf-8')
        with patch('native_mobile.urlopen', return_value=Response(raw)):
            result = api.request('/owned-fixture')
        self.assertEqual(result, expected)
        self.assertEqual(api.token, 'synthetic-opaque-\u00c3\u00a9')

    def test_web_json_escaped_unicode_decodes_once(self):
        raw = json.dumps(self.payload(), ensure_ascii=True).encode('ascii')
        with patch('service.urlopen', return_value=Response(raw)):
            result = MovieBoxService(use_native=False).request('/owned-fixture')
        self.assertEqual(result['subject']['title'], TITLE)

    def test_invalid_utf8_fails_instead_of_silently_creating_mojibake(self):
        malformed = b'{"code":0,"data":{"title":"\xff"}}'
        with patch('service.urlopen', return_value=Response(malformed)):
            with self.assertRaises(UnicodeDecodeError):
                MovieBoxService(use_native=False).request('/owned-fixture')
        with patch('native_mobile.urlopen', return_value=Response(malformed)):
            with self.assertRaises(UnicodeDecodeError):
                NativeMovieBox(host='https://example.test').request('/owned-fixture')


class CacheEncodingTests(unittest.TestCase):
    def test_catalogue_roundtrip_preserves_unicode_and_url_bytes_as_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'catalogue.json'
            store = CatalogueCache(path)
            key = store.key('series', {'genre': 'বাংলা'})
            store.put(key, {'items': [SUBJECT], 'at': 1_000_000_000_000})
            store.flush()
            restored = CatalogueCache(path).get(key)['items'][0]
            self.assertEqual(restored['title'], TITLE)
            self.assertEqual(restored['subjectId'], SUBJECT['subjectId'])
            self.assertEqual(restored['cover']['url'], SUBJECT['cover']['url'])
            self.assertIn(TITLE.encode('utf-8'), path.read_bytes())

    def test_library_and_backup_roundtrip_preserves_international_and_opaque_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'library.json'
            store = LibraryStore(path)
            state = store.load()
            state['saved']['owned'] = copy.deepcopy(SUBJECT)
            state['history']['owned:1:2'] = {'subject': copy.deepcopy(SUBJECT), 'position': 12000}
            store.save(state)
            self.assertEqual(LibraryStore(path).load(), state)
            path.write_bytes(b'invalid JSON')
            recovered = LibraryStore(path)
            self.assertEqual(recovered.load(), state)
            self.assertTrue(recovered.recovered)


class UiLiteralEncodingTests(unittest.TestCase):
    def test_runtime_sources_are_strict_utf8_without_common_double_encoded_literals(self):
        suspicious = re.compile(r'\u00c2[\u0080-\u00bf]|\u00c3[\u0080-\u00bf]|\u00e2(?:\u0080|\u20ac|\u2122)|\u00f0\u0178|\ufffd')
        files = [path for path in ROOT.glob('*.py') if not path.name.startswith(('test_', 'verify_'))]
        for path in files:
            with self.subTest(file=path.name):
                text = path.read_bytes().decode('utf-8-sig', errors='strict')
                self.assertIsNone(suspicious.search(text), path.name)

    def test_actual_qt_metadata_episode_and_player_menu_labels(self):
        # Separate process guarantees app userdata is isolated before importing main.
        code = '''
from PySide6.QtWidgets import QApplication
import main
from smoke import OfflineMediaService
from fluent_ui import stylesheet
app=QApplication([])
app.setStyleSheet(stylesheet('eclipse'))
w=main.Window(api=OfflineMediaService())
subject={'subjectId':'owned-unicode','subjectType':2,'title':'বাংলা · 日本語 – Série “é”','genre':'Drama','countryName':'Côte d’Ivoire'}
w.current=subject
w.detail_loaded({'subject':subject,'isSeries':True,'resource':{'seasons':[{'se':1,'maxEp':2}]}},w.request_generation)
assert w.detail_title.text()==subject['title']
assert '  ·  ' in w.detail_meta.text()
assert w.episode_heading.text()=='Season 1 · 2 episodes'
assert w.subtitle_delay.toolTip()=='Subtitle timing · Positive values display later'
assert any(action.text()=='Import subtitles…' for action in w.subtitle_tools_menu.actions())
w.close()
print('PASS actual Qt UTF-8 metadata, episode and player menu labels')
'''
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, MOVIEBOX_DATA_DIR=folder, QT_QPA_PLATFORM='offscreen')
            result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('PASS actual Qt', result.stdout)


if __name__ == '__main__':
    unittest.main()
