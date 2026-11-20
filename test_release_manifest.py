from pathlib import Path
import json,tempfile,unittest
from tools.check_release import validate

class ReleaseManifestTests(unittest.TestCase):
    def test_readme_cannot_advertise_an_unpublished_future_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);name='MovieBox-Setup-0.10.3-windows-x64.exe'
            (root/'release.json').write_text(json.dumps({'repository':'emransm877/moviebox-desktop','source_version':'0.10.4','published_version':'0.10.3','assets':[name]}),encoding='utf-8')
            (root/'main.py').write_text("APP_VERSION = '0.10.4'",encoding='utf-8')
            link='https://github.com/emransm877/moviebox-desktop/releases/download/v0.10.3/'+name
            (root/'README.md').write_text(link,encoding='utf-8');validate(root)
            (root/'README.md').write_text(link+'\nhttps://github.com/emransm877/moviebox-desktop/releases/latest/download/MovieBox-Setup-0.10.4-windows-x64.exe',encoding='utf-8')
            with self.assertRaises(ValueError):validate(root)
