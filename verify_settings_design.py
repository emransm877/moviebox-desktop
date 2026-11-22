"""Isolated native Settings visual, persistence, keyboard and short-screen QA."""
import argparse,json,os,time
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR']=str(args.output/'isolated-userdata')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QComboBox,QSpinBox,QCheckBox,QPushButton,QScrollArea
from PySide6.QtTest import QTest
from main import Window
from themes import THEMES
from fluent_ui import stylesheet,refresh_theme
from settings_ui import build_settings_dialog
class API:native=None;account_token='';last_play_info={}
app=QApplication([]);app.setStyleSheet(stylesheet('obsidian'));checks={};passed=False
with patch.object(Window,'load_home',lambda self:None),patch.object(Window,'check_optional_updates',lambda *args,**kwargs:None):w=Window(API())
w.update_timer.stop();w.show();w.activateWindow();app.processEvents()
try:
    dialog=build_settings_dialog(w);dialog.show();dialog.activateWindow();QTest.qWait(40)
    assert len(dialog.theme_buttons)==20
    for key,button in dialog.theme_buttons.items():
        button.setFocus();app.processEvents();QTest.keyClick(button,Qt.Key_Space);app.processEvents()
        assert button.isChecked() and w.state['theme']==key and w.state['appearance']=='theme'
        assert app.property('movieboxTheme')==key
        assert not w.theme_navigation.isVisible() and w.sidebar.width()>=200
        assert w.nav_buttons['history'].text()=='History'
        viewport=dialog.findChild(QScrollArea,'themeScroll').viewport();r=button.rect();point=button.mapTo(viewport,r.topLeft())
        assert point.y()>=-2 and point.y()+button.height()<=viewport.height()+2,(key,point.y(),button.height(),viewport.height(),app.focusWidget())
        dialog.grab().save(str(args.output/(key+'.png')))
        checks[key+'_keyboard_theme_live_preview_and_sidebar']=True
    appearance=dialog.findChild(QComboBox,'appearancePicker')
    for index,expected in [(1,'obsidian'),(2,'aurora'),(3,None),(0,None)]:
        appearance.setCurrentIndex(index);app.processEvents()
        if expected:assert w.state['theme']==expected and dialog.theme_buttons[expected].isChecked()
    checks['dark_light_follow_windows_and_theme_modes_retained']=True
    size=dialog.findChild(QSpinBox,'subtitleSize')
    for value in [16,24,44]:
        size.setValue(value);app.processEvents()
        assert w.state['subtitle_size']==value and str(value)+'px' in w.video.caption.styleSheet()
        assert size.lineEdit().contentsRect().width()-14>=size.fontMetrics().horizontalAdvance(size.text())
    checks['subtitle_range_padding_live_caption_and_preview']=True
    updates=dialog.findChild(QCheckBox,'updateNotifications');check=dialog.findChild(QPushButton,'checkUpdates')
    updates.setChecked(False);assert not check.isEnabled() and not w.state['update_notifications']['enabled']
    updates.setChecked(True);assert check.isEnabled() and w.state['update_notifications']['enabled']
    with patch.object(w,'check_optional_updates') as call:check.click();call.assert_called_once_with(force=True)
    checks['optional_update_optout_and_manual_check_retained']=True
    dialog.resize(650,480);app.processEvents()
    last=list(dialog.theme_buttons.values())[-1];last.setFocus();app.processEvents()
    QTest.keyClick(last,Qt.Key_Tab);assert app.focusWidget() is appearance
    QTest.keyClick(appearance,Qt.Key_Tab);assert app.focusWidget() is size
    QTest.keyClick(size,Qt.Key_Tab);assert app.focusWidget() is updates
    QTest.keyClick(updates,Qt.Key_Tab);assert app.focusWidget() is check
    QTest.keyClick(check,Qt.Key_Tab);assert app.focusWidget() is dialog.findChild(QPushButton,'settingsDone')
    assert dialog.findChild(QPushButton,'settingsDone').isVisible()
    dialog.grab().save(str(args.output/'short-screen-keyboard.png'))
    checks['short_screen_scroll_and_all_controls_keyboard_accessible']=True
    dialog.findChild(QPushButton,'settingsDone').click();assert not dialog.isVisible()
    checks['done_closes_saved_settings']=True
    passed=True
finally:
    w.close();app.processEvents();(args.output/'result.json').write_text(json.dumps({'passed':passed,'checks':checks,'scope':'Actual Qt widgets; isolated state and synthetic API only. No normal account/history or external update request.'},indent=2),encoding='utf-8')
print(json.dumps({'passed':passed,'checks':len(checks)}))
