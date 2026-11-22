"""Delayed image completion must never put another title's artwork on a slide."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QBuffer,QByteArray,QIODevice
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from fluent_ui import HeroCard

class Owner:
    def __init__(self): self.jobs=[]; self.state={'saved': {}};self.opened=[]
    def submit(self,load,ready,**kwargs): self.jobs.append((load,ready))
    def open_detail(self,subject):self.opened.append(subject)

def png(color,width=1920,height=1080):
    image=QImage(width,height,QImage.Format_RGB32); image.fill(QColor(color))
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG')
    return bytes(data)

class HeroArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setProperty('movieboxTheme','eclipse');cls.app.setProperty('movieboxDark',True)
    def test_card_details_target_own_subject_without_instant_play_or_redundant_actions(self):
        from PySide6.QtWidgets import QPushButton
        owner=Owner();owner.hero_auto_play='old'
        card=HeroCard(owner,lambda _:b'');card.timer.stop()
        subject={'subjectId':'own-title','title':'Own title'};card.set_subject(subject);card.card_detail(subject)
        self.assertEqual(owner.opened,[subject]);self.assertEqual(owner.hero_auto_play,'')
        self.assertFalse(card.findChildren(QPushButton));card.close()
    def test_late_previous_slide_cannot_overwrite_current_slide(self):
        owner=Owner();images={'a':png('red'),'b':png('blue')}
        card=HeroCard(owner,images.__getitem__);card.timer.stop()
        for identity in ['a','b']:
            card.set_subject({'subjectId':identity,'title':identity,'stills':{'url':identity,'width':1920,'height':1080}})
        load,ready=owner.jobs[1];ready(load())
        load,ready=owner.jobs[0];ready(load())
        self.assertEqual(card.subject['subjectId'],'b')
        self.assertEqual(card.image.toImage().pixelColor(20,20),QColor('blue'))
        card.set_subject({'subjectId':'missing','title':'missing'})
        self.assertTrue(card.image.isNull())
        load,ready=owner.jobs[1];ready(load())
        self.assertTrue(card.image.isNull());card.close()
    def test_small_actual_image_rejected_even_with_false_hd_metadata(self):
        owner=Owner();card=HeroCard(owner,lambda _:png('red',600,338));card.timer.stop()
        card.set_subject({'subjectId':'small','title':'small','stills':{'url':'small','width':1920,'height':1080}})
        load,ready=owner.jobs[0];ready(load())
        self.assertTrue(card.image.isNull());card.close()
    def test_genuine_lower_resolution_landscape_decodes_consistently_with_metadata_gate(self):
        owner=Owner();card=HeroCard(owner,lambda _:png('blue',920,518));card.timer.stop()
        card.set_subject({'subjectId':'campus','title':'Campus','banner':{'url':'owned-wide','width':920,'height':518}})
        load,ready=owner.jobs[-1];ready(load())
        self.assertFalse(card.image.isNull());self.assertFalse(card.poster_mode);card.close()
    def test_missing_banner_uses_same_subject_contained_poster_composition(self):
        owner=Owner();card=HeroCard(owner,lambda _:png('green',600,900));card.timer.stop()
        card.set_subject({'subjectId':'poster-title','title':'Poster title','cover':{'url':'same-subject-poster'}})
        load,ready=owner.jobs[-1];ready(load())
        self.assertTrue(card.poster_mode);self.assertFalse(card.image.isNull());self.assertIsNone(card.banner_source)
        card.set_subject({'subjectId':'next','title':'Next'})
        ready(load());self.assertTrue(card.image.isNull());card.close()
