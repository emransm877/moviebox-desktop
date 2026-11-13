"""Live native GUI verification. Invoked explicitly with --smoke-test."""
import ctypes
import json
import time
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import QUrl
from pathlib import Path


class SmokeTest(QObject):
    def __init__(self, window, output, media_test=''):
        super().__init__(window)
        self.w, self.output = window, output
        output.mkdir(parents=True, exist_ok=True)
        self.result = {'checks': {}, 'errors': [], 'started': time.time()}
        self.start = time.monotonic()
        self.media_test = media_test
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

    def tick(self):
        try:
            (self.output / 'heartbeat.json').write_text(json.dumps({'step': self.step, 'status': self.w.status.text(), 'jobs':len(self.w.jobs), 'position':self.w.player.position(), 'frames':self.w.frames, 'elapsed':time.monotonic()-self.start}), encoding='utf-8')
            self.advance()
        except Exception as error:
            self.result['errors'].append(str(error))
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
                self.result['media_test_source'] = 'Blender Sintel 1080p trailer, separate from MovieBox service playback'
                w.playing_key = ''
                w.playing_subject = None
                w.current_stream = None
                w.now_title.setText('1080p native playback verification · Sintel')
                w.start_video(QUrl.fromLocalFile(str(Path(self.media_test).resolve())).toString())
            else:
                w.watch_current()
        elif self.step == 'playing' and w.frames > 30 and w.player.position() > 3000:
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
