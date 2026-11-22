"""Windows offscreen smoke must test real font geometry, not dummy glyph boxes."""
import json,os,subprocess,sys,unittest


class SmokeEnvironmentTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows installed-font smoke bootstrap')
    def test_empty_offscreen_font_database_gets_real_metrics_before_widgets(self):
        code='''
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontMetrics
from smoke import prepare_smoke_environment
app=QApplication([])
setup=prepare_smoke_environment(app)
font=QFont('Segoe UI');font.setPixelSize(16)
print(json.dumps({'setup':setup,'width':QFontMetrics(font).horizontalAdvance('Seasons & episodes')}))
'''
        result=subprocess.run([sys.executable,'-c',code],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertGreater(data['setup']['font_families_after'],0)
        self.assertLess(data['width'],220)  # Empty database measures this title at 288 px.
        if not data['setup']['font_families_before']:self.assertTrue(data['setup']['registered'])


if __name__=='__main__':unittest.main()
