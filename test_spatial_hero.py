"""Shared geometry, real OS motion guard, recycle identity and bounded artwork."""
import ctypes,math,os,unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal
from PySide6.QtGui import QPixmap,QColor
from PySide6.QtWidgets import QApplication,QWidget
from themes import THEMES,THEME_SPEC
from spatial_hero import SpatialHero


class Art(QObject):
    changed=Signal()
    def __init__(self):super().__init__();self.calls=[];self.images=False
    def get(self,url):
        self.calls.append(url)
        if not self.images:return None
        image=QPixmap(10,15);image.fill(QColor('green'));return image


class SpatialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.app.setProperty('movieboxTheme','obsidian');self.owner=QWidget();self.owner.art=Art();self.owner.poster_delegate=SimpleNamespace(motion=False)
        self.owner.stack=SimpleNamespace(currentIndex=lambda:0);self.owner.rotation_paused=True
        self.scene=SpatialHero(self.owner,self.owner);self.scene.resize(1180,304)
        self.subjects=[{'subjectId':str(i),'title':'Owned fixture '+str(i),'cover':{'url':'fixture://'+str(i)}} for i in range(100)]
    def tearDown(self):self.scene.animation.stop();self.scene.auto.stop();self.owner.close();self.owner.deleteLater()

    def test_all_twenty_projected_geometries_are_finite_and_request_visible_plus_two(self):
        self.scene.set_subjects(self.subjects)
        for key in THEMES:
            self.owner.art.calls=[];self.app.setProperty('movieboxTheme',key);self.scene.apply_theme()
            spec=self.scene.geometry_spec
            self.assertEqual(len(self.scene.actors),spec['visibleCards'])
            self.assertLessEqual(len(set(self.owner.art.calls)),spec['visibleCards']+2)
            for slot in spec['slots']:
                polygon,width,height=self.scene.polygon(slot)
                self.assertGreater(width,0);self.assertGreater(height,0)
                self.assertTrue(all(math.isfinite(point.x()) and math.isfinite(point.y()) for point in polygon))
                self.assertGreater(polygon.boundingRect().width(),.01);self.assertGreater(polygon.boundingRect().height(),.01)

    def test_recycled_identity_changes_only_while_invisible(self):
        self.scene.set_subjects(self.subjects)
        with patch.object(self.scene,'motion_allowed',return_value=True):self.scene.advance(1)
        actor=next(a for a in self.scene.actors if a['recycled']);self.scene.animation.stop()
        self.scene.progress=.1;slot,subject=self.scene.current(actor);self.assertEqual(subject,actor['old_subject'])
        self.scene.progress=.22;slot,subject=self.scene.current(actor);self.assertEqual(subject,actor['subject']);self.assertEqual(slot['opacity'],0)
        self.scene.progress=.8;slot,subject=self.scene.current(actor);self.assertEqual(subject,actor['subject']);self.assertGreater(slot['opacity'],0)

    def test_hero_lru_is_bounded_and_does_not_copy_full_size_sources(self):
        self.owner.art.images=True
        for subject in self.subjects:self.scene.poster(subject)
        self.assertEqual(len(self.scene.cache),24)
        self.assertEqual(self.scene.memory_metrics()['decoded_bytes_upper_bound'],24*10*15*4)

    @unittest.skipUnless(os.name=='nt','Windows native preference guard')
    def test_real_windows_animation_preference_api_is_used(self):
        self.owner.poster_delegate.motion=True
        def disabled(action,zero,pointer,last):
            self.assertEqual(action,0x1042);ctypes.cast(pointer,ctypes.POINTER(ctypes.c_int))[0]=0;return 1
        with patch('spatial_hero.ctypes.windll.user32.SystemParametersInfoW',side_effect=disabled) as query:
            self.assertFalse(self.scene.motion_allowed());query.assert_called_once()

    def test_all_theme_text_and_button_colours_have_readable_contrast(self):
        def luminance(hex_value):
            channels=[int(hex_value[i:i+2],16)/255 for i in (1,3,5)]
            channels=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
            return sum(c*w for c,w in zip(channels,[.2126,.7152,.0722]))
        for key,p in THEMES.items():
            for foreground,background in [('text','panel'),('secondary','panel'),('ink','accent')]:
                a,b=luminance(p[foreground]),luminance(p[background]);ratio=(max(a,b)+.05)/(min(a,b)+.05)
                self.assertGreaterEqual(ratio,4.5,(key,foreground,ratio))

    def test_input_idle_deadline_focus_alone_and_persistent_explicit_pause(self):
        self.scene.set_subjects(self.subjects);self.owner.rotation_paused=False;self.scene.last_manual=100
        with patch.object(self.scene,'isVisible',return_value=True),patch.object(self.scene,'motion_allowed',return_value=True),patch.object(self.owner,'isActiveWindow',return_value=True),patch.object(QApplication,'focusWidget',return_value=self.scene),patch.object(self.scene,'advance') as advance:
            with patch('spatial_hero.time.monotonic',return_value=107.999):
                self.scene.automatic();advance.assert_not_called();self.assertLessEqual(self.scene.auto.interval(),2)
            with patch('spatial_hero.time.monotonic',return_value=108):
                self.scene.automatic();advance.assert_called_once_with(1,False)
            advance.reset_mock();self.owner.rotation_paused=True
            with patch('spatial_hero.time.monotonic',return_value=120):self.scene.automatic();advance.assert_not_called()
            self.owner.rotation_paused=False
            with patch('spatial_hero.time.monotonic',return_value=108.84):self.scene.complete();self.assertEqual(self.scene.auto.interval(),6000-self.scene.animation.duration())


if __name__=='__main__':unittest.main()
