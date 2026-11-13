"""Real Qt theme/settings/hero regression with isolated data and local artwork."""
import json,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'verification/themes-v070';OUT.mkdir(parents=True,exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR']=str(OUT/'user-data')
from PySide6.QtWidgets import QApplication,QComboBox,QDialog,QSpinBox,QStyle,QStyleOptionSpinBox
from PySide6.QtCore import Qt,QTimer,QUrl
from PySide6.QtGui import QColor,QPixmap
from PySide6.QtTest import QTest
import main
from fluent_ui import stylesheet,open_settings,refresh_theme
from themes import THEMES
main.Window.load_home=lambda self:None
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(stylesheet('obsidian'))
w=main.Window();w.update_timer.stop();w.state['update_notifications']['enabled']=False
w.resize(1440,940);w.show();app.processEvents()
items=[{'subjectId':str(i),'subjectType':1 if i%2==0 else 2,'title':f'Spotlight title {i}','releaseDate':'2026-11-01','cover':{'url':'fixture://cover'}} for i in range(100)]
cover=QPixmap(300,450);cover.fill(QColor('#35556e'));w.art.images['fixture://cover']=cover
w.hero.set_slides(items);w.show_items(items[:24]);app.processEvents()
checks={}
original_saved=dict(w.state['saved'])
for key in THEMES:
    def choose():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,QDialog)
        combo=dialog.findChild(QComboBox,'themePicker')
        combo.setFocus();index=list(THEMES).index(key)
        if combo.currentIndex()==index:combo.currentIndexChanged.emit(index)
        else:combo.setCurrentIndex(index)
        assert w.state['theme']==key
        QTimer.singleShot(80,dialog.accept)
    QTimer.singleShot(80,choose);open_settings(w);QTest.qWait(50)
    assert app.property('movieboxTheme')==key
    assert w.theme_navigation.isVisible()==(THEMES[key]['layout']=='top')
    assert w.brand_logo.isVisible() and not w.brand_logo.pixmap().isNull()
    for nav in w.theme_nav_buttons.values():
        if nav.isVisible():assert nav.width()>=nav.label_width
    assert w.hero.info.isEnabled() and w.hero.next.isEnabled()
    for control in (w.hero.explore,w.hero.info,w.hero.save,w.hero.previous,w.hero.next,w.hero.pause_rotation,w.hero.counter):
        assert control.geometry().right()<=w.hero.width(),(key,control.text(),control.geometry(),w.hero.size())
    assert w.state['saved']==original_saved
    w.grab().save(str(OUT/(key+'.png')))
    checks[key+'_live_settings_and_layout']=True
seen=[];w.open_detail=lambda subject:seen.append(subject['subjectId'])
w.hero.advance(1);active=w.hero.subject['subjectId'];w.hero.info.click()
assert seen[-1]==active and not w.hero_auto_play
w.hero.explore.click();assert seen[-1]==active and w.hero_auto_play==active
w.hero.next.setFocus();old=w.hero.subject;w.hero.advance(1,automatic=True);assert w.hero.subject is old
w.hero.set_slides(items[20:]);assert w.hero.subject is old
checks['active_slide_watch_and_info_target_exact_subject']=True
checks['focused_controls_freeze_rotation_and_feed_replacement']=True
w.hero.toggle_rotation();old=w.hero.subject;w.hero.advance(1,automatic=True);assert w.hero.subject is old
checks['explicit_pause_preserves_slide']=True
w.state['theme']='eclipse';w.persist();assert main.load_state()['theme']=='eclipse'
checks['selected_theme_persists_without_changing_library']=True
# A live theme change must not reset the native player or its source/position.
media=ROOT/'verification/sintel-1080p.mp4'
w.player.setSource(QUrl.fromLocalFile(str(media)));w.player.play()
deadline=time.monotonic()+12
while w.player.position()<300 and time.monotonic()<deadline:QTest.qWait(50)
assert w.player.position()>0
w.player.pause();source=w.player.source();position=w.player.position()
for key in THEMES:
    refresh_theme(w,key);app.processEvents()
    assert w.player.source()==source and abs(w.player.position()-position)<100
    w.stack.setCurrentIndex(2)
    w.toggle_fullscreen();QTest.qWait(30)
    assert w.cinema.isVisible() and w.cinema.isFullScreen()
    w.toggle_fullscreen();QTest.qWait(30)
    assert not w.cinema.isVisible() and w.player.source()==source
checks['all_themes_preserve_native_player_source_and_position']=True
checks['all_themes_preserve_true_fullscreen_enter_and_exit']=True
def check_appearance():
    dialog=QApplication.activeModalWidget()
    picker=dialog.findChild(QComboBox,'appearancePicker')
    assert picker.count()==4
    spin=dialog.findChild(QSpinBox,'subtitleSize')
    option=QStyleOptionSpinBox();spin.initStyleOption(option)
    edit=spin.style().subControlRect(QStyle.CC_SpinBox,option,QStyle.SC_SpinBoxEditField,spin)
    assert spin.lineEdit().textMargins().left()>=12,(edit,spin.size())
    spin.grab().save(str(OUT/'subtitle-size-padding.png'))
    picker.setCurrentIndex(2);assert app.property('movieboxTheme')=='aurora'
    picker.setCurrentIndex(1);assert app.property('movieboxTheme')=='obsidian'
    picker.setCurrentIndex(3);assert w.state['appearance']=='system'
    assert dialog.height()<=QApplication.primaryScreen().availableGeometry().height()
    dialog.accept()
QTimer.singleShot(80,check_appearance);open_settings(w)
checks['legacy_dark_light_follow_windows_and_scrollable_settings_retained']=True
checks['theme_logo_visible_and_navigation_labels_have_measured_width']=True
w.stack.setCurrentIndex(1);app.processEvents()
wide=QPixmap(480,270);wide.fill(QColor('#2d7892'));w.detail_cover.setPixmap(wide)
for width,height in ((255,382),(210,315)):
    w.detail_cover.setFixedSize(width,height);app.processEvents()
    fitted=w.detail_cover.pixmap()
    assert abs(fitted.width()/fitted.height()-480/270)<.02
    assert fitted.width()<=width and fitted.height()<=height
checks['wide_detail_artwork_preserves_aspect_after_resize']=True
w.detail_title.setText('A movie with a short synopsis')
w.description.setText('A short synopsis stays next to the Watch controls.')
w.season_row.hide();app.processEvents()
assert 0<=w.watch.geometry().top()-w.description.geometry().bottom()<=24
checks['movie_watch_controls_follow_synopsis_without_flexible_gap']=True
w.season.addItem('Season 1',{'se':1,'maxEp':2})
w.season_row.show();w.season.show();app.processEvents()
assert 0<=w.season_row.geometry().top()-w.description.geometry().bottom()<=24
assert 0<=w.watch.geometry().top()-w.season_row.geometry().bottom()<=24
checks['series_season_controls_remain_between_synopsis_and_actions']=True
checks['passed']=True
(OUT/'result.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(json.dumps(checks,indent=2));w.close();app.processEvents()
