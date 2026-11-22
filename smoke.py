"""Native GUI verification; --media-test uses an offline catalogue fixture."""
import ctypes
import json
import time
import copy
import os
import traceback
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import QUrl
from pathlib import Path


def prepare_smoke_environment(app):
    """Give Windows' offscreen test plugin real installed font metrics."""
    from PySide6.QtGui import QFontDatabase
    setup={'platform':app.platformName(),'font_families_before':len(QFontDatabase.families()),'registered':[]}
    if os.name=='nt' and app.platformName()=='offscreen' and not setup['font_families_before']:
        directory=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'
        for name in ('SegUIVar.ttf','segoeui.ttf','seguisb.ttf','segoeuib.ttf'):
            path=directory/name
            if path.is_file():
                handle=QFontDatabase.addApplicationFont(str(path))
                if handle>=0:setup['registered'].extend(QFontDatabase.applicationFontFamilies(handle))
        if not QFontDatabase.families():
            raise RuntimeError('Offscreen smoke has no usable installed fonts; run the native Windows platform instead.')
    setup['font_families_after']=len(QFontDatabase.families());app.setProperty('movieboxSmokeFontSetup',setup)
    return setup


class OfflineMediaService:
    """Catalogue scaffolding only; playback uses the explicit owned local file."""
    native = None
    account_token = ''
    last_play_info = {}
    subject = {'subjectId': 'offline-media-smoke', 'subjectType': 1,
               'title': 'Interstellar offline smoke fixture',
               'description': 'Synthetic catalogue title for offline packaged player checks.'}

    def home(self):
        return {'operatingList': [{'title': 'Offline fixture', 'subjects': [dict(self.subject)]}]}

    def search(self, *_):
        return {'items': [dict(self.subject)], 'pager': {'hasMore': False}}

    def detail(self, subject):
        return {'subject': subject, 'resource': {'seasons': []}}


class SmokeTest(QObject):
    def __init__(self, window, output, media_test=''):
        super().__init__(window)
        self.w, self.output = window, output
        output.mkdir(parents=True, exist_ok=True)
        self.result = {'checks': {}, 'errors': [], 'started': time.time()}
        self.result['diagnostics']={'font_setup':QApplication.instance().property('movieboxSmokeFontSetup')}
        self.start = time.monotonic()
        self.media_test = media_test
        self.result['scope'] = 'Offline catalogue fixture and supplied local media' if media_test else 'Live upstream service'
        if media_test:
            window.schedule_prefetch = lambda: None
            window.update_timer.stop()
            window.state['update_notifications']['enabled'] = False
        self.ui_gaps = []
        self.play_ui_gaps = []
        self.last_tick = time.monotonic()
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.watch_ui)
        self.ui_timer.start(16)
        self.step = 'catalog'
        self.t = QTimer(self)
        self.t.timeout.connect(self.tick)
        self.t.start(500)
        window.audio.setMuted(True)
        window.player.errorOccurred.connect(lambda error, text: self.result['errors'].append(text))

    def watch_ui(self):
        now = time.monotonic()
        self.ui_gaps.append((now - self.last_tick) * 1000)
        if self.w.player.isPlaying() and self.w.frames > 5:
            self.play_ui_gaps.append((now - self.last_tick) * 1000)
        self.last_tick = now

    def check_player_contract(self):
        """Exercise packaged input/layering against the explicitly owned media."""
        from PySide6.QtCore import Qt,QPoint,QEvent
        from PySide6.QtTest import QTest
        w=self.w;volume=w.volume.value();muted=w.audio.isMuted()
        w.video.setFocus();QTest.keyClick(w.video,Qt.Key_Up)
        assert w.volume.value()==min(100,volume+5)
        QTest.keyClick(w.video,Qt.Key_Down);assert w.volume.value()==max(0,min(100,volume+5)-5)
        w.volume.setValue(volume);w.audio.setMuted(muted)
        self.result['checks']['packaged_playback_up_down_volume']=True
        saved=(w.playing_subject,w.playing_key,w.detail_data,w.episode_browser_button.isVisible())
        try:
            w.playing_subject={'subjectId':'owned-smoke-drawer','subjectType':2,'title':'Owned drawer fixture'};w.playing_key='owned-smoke-drawer:1:1';w.detail_data={'resource':{'seasons':[{'se':1,'maxEp':6}]}}
            w.open_player_episodes();QApplication.processEvents()
            point=w.video.mapToGlobal(QPoint(8,8));panel=w.player_episode_panel
            diagnostics={'platform':QApplication.platformName(),'width':panel.width(),'height':panel.height(),'panel_visible':panel.isVisible(),'panel_geometry':panel.frameGeometry().getRect(),'video_geometry':w.video.geometry().getRect(),'outside_global':[point.x(),point.y()],'point_inside_panel':panel.frameGeometry().contains(point),'popup':type(QApplication.activePopupWidget()).__name__}
            self.result.setdefault('diagnostics',{})['drawer_open']=diagnostics
            assert 220<=panel.width()<=300,'Compact episode drawer width: '+str(diagnostics)
            state=w.player.playbackState();events=[]
            class MouseTrace(QObject):
                def eventFilter(self,obj,event):
                    if event.type() in (QEvent.MouseButtonPress,QEvent.MouseButtonRelease):
                        position=event.globalPosition();events.append({'event':event.type().name,'target':obj.metaObject().className(),'global':[position.x(),position.y()]})
                    return False
            trace=MouseTrace();QApplication.instance().installEventFilter(trace)
            try:QTest.mouseClick(w.video,Qt.LeftButton,pos=QPoint(8,8))
            finally:QApplication.instance().removeEventFilter(trace)
            after={'panel_visible':panel.isVisible(),'playback_before':str(state),'playback_after':str(w.player.playbackState()),'dismiss_press':getattr(w.input_router,'drawer_dismiss_press',False),'events':events}
            self.result['diagnostics']['drawer_outside']=after
            assert not panel.isVisible(),'Outside click did not dismiss episode drawer: '+str(after)
            assert w.player.playbackState()==state,'Outside click altered playback: '+str(after)
            self.result['checks']['packaged_compact_drawer_outside_click_no_playback_toggle']=True
        finally:
            w.close_player_episodes();w.playing_subject,w.playing_key,w.detail_data,visible=saved;w.episode_browser_button.setVisible(visible);w.video.setFocus()

    def check_home_contract(self,duration):
        """Private in-memory fixtures verify frozen modules and bundled spec."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage,QColor
        from PySide6.QtWidgets import QPushButton,QScrollArea
        from PySide6.QtTest import QTest
        from themes import THEMES,THEME_EFFECTS
        from settings_ui import build_settings_dialog
        from fluent_ui import refresh_theme,set_nav
        assert os.environ.get('MOVIEBOX_DATA_DIR'),'Offline UI smoke requires an isolated MOVIEBOX_DATA_DIR'
        w=self.w;original=copy.deepcopy(w.state);original_slides=list(w.hero.slides);old_theme=QApplication.instance().property('movieboxTheme');original_persist=w.persist;motion=w.poster_delegate.motion
        try:
            w.persist=lambda:None;w.poster_delegate.motion=False;subjects=[]
            for i in range(100):
                path=self.output/f'owned-ui-{i}.png';image=QImage(120,180,QImage.Format_RGB32);image.fill(QColor.fromHsv(i*3%360,120,170));assert image.save(str(path))
                subjects.append({'subjectId':'owned-ui-'+str(i),'subjectType':1,'title':'Owned UI fixture '+str(i),'releaseDate':'2026','cover':{'url':QUrl.fromLocalFile(str(path.resolve())).toString()}})
            duration=max(4000,int(duration));w.state['history']={s['subjectId']+':0:0':{'subject':s,'position':duration//(4-i),'duration':duration,'updated':3-i} for i,s in enumerate(subjects[:3])}
            set_nav(w,'home');w.hero.rotation_paused=True;w.hero.set_slides(subjects);w.stack.setCurrentIndex(0);w.hero.show();w.continue_strip.refresh()
            assert len(THEMES)==20;ids=[]
            for key in THEMES:
                w.state['theme']=key;w.state['appearance']='theme';refresh_theme(w,key);QApplication.processEvents()
                assert w.hero.spatial.geometry_spec['id']==THEME_EFFECTS[key]['id'];assert len(w.hero.spatial.actors)==THEME_EFFECTS[key]['visibleCards'];ids.append(THEME_EFFECTS[key]['id'])
            assert not w.hero.findChildren(QPushButton)
            assert sum(card.isVisible() for card in w.continue_strip.cards)==3
            self.result['checks']['packaged_twenty_theme_assets_and_geometries']=len(ids)==len(set(ids))==20
            self.result['checks']['packaged_hero_has_no_redundant_control_row']=True
            self.result['checks']['packaged_continue_uses_private_history_progress']=all(card.record['duration']==duration and card.record['position']>0 for card in w.continue_strip.cards)
            dialog=build_settings_dialog(w);inspection_errors=[]
            def inspect_settings():
                try:
                    assert len(dialog.theme_buttons)==20,'Settings must expose all 20 theme choices'
                    if QApplication.platformName()=='offscreen':QApplication.setActiveWindow(dialog)
                    last=list(dialog.theme_buttons.values())[-1];last.setFocus(Qt.TabFocusReason);QApplication.processEvents()
                    viewport=dialog.findChild(QScrollArea,'themeScroll').viewport();point=last.mapTo(viewport,last.rect().topLeft())
                    focus=QApplication.focusWidget();details={'last_theme_y':point.y(),'button_height':last.height(),'viewport_height':viewport.height(),'focused':focus.objectName() if focus else None,'modal':QApplication.activeModalWidget() is dialog}
                    self.result.setdefault('diagnostics',{})['settings_keyboard']=details
                    assert point.y()>=-2 and point.y()+last.height()<=viewport.height()+2,'Last theme is not visible after keyboard focus: '+str(details)
                    dialog.grab().save(str(self.output/'settings-20-themes.png'))
                except Exception as error:
                    inspection_errors.append(error);(self.output/'settings-failure-traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
                finally:dialog.reject()
            QTimer.singleShot(80,inspect_settings)
            dialog.exec()  # Match the actual Settings user flow, including focus activation.
            if inspection_errors:raise inspection_errors[0]
            if QApplication.platformName()=='offscreen':QApplication.setActiveWindow(w)
            self.result['checks']['packaged_settings_twenty_keyboard_reachable_choices']=True
            scene=w.hero.spatial;scene.setFocus();before=scene.index;QTest.keyClick(scene,Qt.Key_Right);assert scene.index==(before+1)%100
            opened=[];open_detail=w.open_detail
            try:
                w.open_detail=lambda subject:opened.append(subject['subjectId']);QTest.keyClick(scene,Qt.Key_Return)
                assert opened==[scene.subjects[scene.index]['subjectId']]
            finally:w.open_detail=open_detail
            self.result['checks']['packaged_keyboard_opens_exact_poster_details']=True
            w.grab().save(str(self.output/'home-20-theme-contract.png'))
        finally:
            w.search.setFocus();w.state=original;w.persist=original_persist;w.poster_delegate.motion=motion;refresh_theme(w,old_theme);w.hero.set_slides(original_slides);w.continue_strip.refresh()

    def tick(self):
        try:
            (self.output / 'heartbeat.json').write_text(json.dumps({'step': self.step, 'status': self.w.status.text(), 'jobs':len(self.w.jobs), 'position':self.w.player.position(), 'frames':self.w.frames, 'elapsed':time.monotonic()-self.start}), encoding='utf-8')
            self.advance()
        except Exception as error:
            self.result['errors'].append(str(error) or type(error).__name__)
            (self.output/'failure-traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
            self.finish(False)

    def advance(self):
        w = self.w
        if time.monotonic() - self.start > 90:
            self.result['errors'].append('Timed out at ' + self.step + ': ' + w.status.text())
            self.finish(False)
            return
        if self.step == 'catalog' and w.catalog_model.items:
            self.result['checks']['catalog_count'] = sum(len(row) for row in w.sections.values())
            w.grab().save(str(self.output / 'catalog.png'))
            self.sample = next((s for row in w.sections.values() for s in row if s['subjectId'] == '6853990427147001176'), w.catalog_model.items[0])
            self.step = 'search'
            w.search.setText('Interstellar')
            w.run_search()
        elif self.step == 'search' and not w.jobs and w.heading.text() == 'Search results':
            if not w.catalog_model.items:
                raise AssertionError('Search returned no results: ' + w.status.text())
            self.result['checks']['search_count'] = len(w.catalog_model.items)
            self.result['checks']['search_has_match'] = any('interstellar' in s['title'].lower() for s in w.catalog_model.items)
            w.grab().save(str(self.output / 'search.png'))
            self.step = 'detail'
            w.open_detail(self.sample)
        elif self.step == 'detail' and w.detail_data and w.watch.isEnabled():
            self.result['checks']['description_loaded'] = len(w.description.text()) > 30
            self.result['checks']['seasons'] = w.season.count()
            key = str(w.current['subjectId'])
            previous = dict(w.state['saved'])
            w.toggle_saved()
            self.result['checks']['watchlist_toggle'] = (key in w.state['saved']) != (key in previous)
            w.state['saved'] = previous
            w.persist()
            w.grab().save(str(self.output / 'detail.png'))
            self.step = 'playing'
            if self.media_test:
                self.result['media_test_source'] = Path(self.media_test).name
                w.playing_key = ''
                w.playing_subject = None
                w.current_stream = None
                w.now_title.setText('Local native playback verification · ' + Path(self.media_test).name)
                w.start_video(QUrl.fromLocalFile(str(Path(self.media_test).resolve())).toString())
            else:
                w.watch_current()
        elif self.step == 'playing' and w.frames > 30 and w.player.position() > 3000:
            if self.media_test:self.check_player_contract()
            self.result['checks']['video_frames'] = w.frames
            self.result['checks']['position_ms'] = w.player.position()
            self.result['checks']['duration_ms'] = w.player.duration()
            self.result['checks']['unlocked_qualities'] = [s.get('resolutions') for s in w.streams]
            self.result['checks']['selected_quality'] = w.quality.currentText()
            self.result['checks']['video_resolution'] = [w.video.videoSink().videoSize().width(), w.video.videoSink().videoSize().height()]
            self.result['checks']['seekable'] = w.player.isSeekable()
            self.result['checks']['subtitle_languages'] = [w.caption_selector.itemText(i) for i in range(1, w.caption_selector.count())]
            w.player.pause()
            self.result['checks']['pause'] = w.player.playbackState() == QMediaPlayer.PausedState
            w.player.play()
            w.save_progress()
            if not self.media_test:
                self.result['checks']['resume_saved'] = w.playing_key in w.state['history']
            if self.media_test:
                from playback import parse_subtitles
                w.subtitle_track.set(parse_subtitles('1\n00:00:00,000 --> 00:02:00,000\nNative Windows subtitle rendering check'))
                w.position_changed(w.player.position())
                self.result['checks']['subtitle_overlay_visible'] = w.video.caption.isVisible()
                self.seek_target = 15000
                self.seek_frames = w.frames
                self.step = 'seek'
                w.player.setPosition(self.seek_target)
            else:
                if w.caption_selector.count() > 1:
                    w.caption_selector.setCurrentIndex(1)
                    self.step = 'captions'
                else:
                    raise AssertionError('No subtitles were returned for the known subtitle-enabled test title.')
        elif self.step == 'captions' and w.subtitle_track.cues:
            cues = w.subtitle_track.cues
            self.result['checks']['online_subtitle_cues'] = len(cues)
            cue = next((cue for cue in cues if cue.start >= 60000 and cue.end - cue.start >= 2000), cues[0])
            self.seek_target = cue.start + min(500, (cue.end - cue.start) // 3)
            self.seek_frames = w.frames
            self.step = 'seek'
            w.player.setPosition(self.seek_target)
        elif self.step == 'seek' and w.player.position() >= self.seek_target and w.frames > self.seek_frames + 10:
            self.result['checks']['seek_completed_ms'] = w.player.position()
            self.result['checks']['subtitle_overlay_visible'] = w.video.caption.isVisible()
            if hasattr(w, 'last_frame'):
                image = w.last_frame.toImage()
                image.save(str(self.output / 'decoded-frame.png'))
                small = image.scaled(64, 64)
                self.result['checks']['decoded_nonblack_samples'] = sum(small.pixelColor(x, y).value() > 15 for x in range(small.width()) for y in range(small.height()))
            w.grab().save(str(self.output / 'playback.png'))
            self.finish(True)

    def finish(self, passed):
        self.t.stop()
        self.ui_timer.stop()
        self.result['passed'] = passed and not self.result['errors']
        self.result['elapsed_seconds'] = round(time.monotonic() - self.start, 2)
        self.result['status'] = self.w.status.text()
        gaps = sorted(self.ui_gaps)
        if gaps:
            self.result['ui_timer_gap_p95_ms'] = round(gaps[int(len(gaps) * .95)], 1)
            self.result['ui_timer_gap_max_ms'] = round(max(gaps), 1)
        if self.play_ui_gaps:
            gaps = sorted(self.play_ui_gaps)
            self.result['playback_ui_timer_gap_p95_ms'] = round(gaps[int(len(gaps) * .95)], 1)
            self.result['playback_ui_timer_gap_max_ms'] = round(max(gaps), 1)
        class Counters(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [(n, ctypes.c_size_t) for n in ['peak', 'working', 'pagePeak', 'page', 'nonPagePeak', 'nonPage', 'pagefile', 'pagefilePeak']]
        c = Counters()
        c.cb = ctypes.sizeof(c)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        ctypes.windll.psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb)
        self.result['working_set_mb'] = round(c.working / 1024 / 1024, 1)
        self.w.grab().save(str(self.output / 'final.png'))
        self.w.show_discover()
        if self.media_test and passed:
            try:self.check_home_contract(self.w.player.duration())
            except Exception as error:
                self.result['errors'].append('Packaged home contract: '+(str(error) or type(error).__name__));self.result['passed']=False
                (self.output/'home-failure-traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        self.w.grab().save(str(self.output / 'home-complete.png'))
        from fluent_ui import refresh_theme, open_settings
        def capture_settings():
            dialog = QApplication.activeModalWidget()
            if dialog is None:
                dialog = next((widget for widget in self.w.findChildren(QDialog) if widget.windowTitle() == 'MovieBox settings'), None)
            if dialog:
                dialog.grab().save(str(self.output / 'settings.png'))
                dialog.reject()
        QTimer.singleShot(200, capture_settings)
        open_settings(self.w)
        refresh_theme(self.w, False)
        self.w.grab().save(str(self.output / 'home-light.png'))
        refresh_theme(self.w, True)
        (self.output / 'result.json').write_text(json.dumps(self.result, indent=2), encoding='utf-8')
        self.w.close()
        QApplication.instance().exit(0 if self.result['passed'] else 1)
