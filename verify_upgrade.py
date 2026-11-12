"""Isolated live acceptance checks for desktop playback and input behavior."""
import json
import os
from pathlib import Path
import time
import traceback
import faulthandler
faulthandler.dump_traceback_later(35, repeat=True)

ROOT = Path(__file__).parent
OUT = ROOT / 'verification' / 'upgrade-v03'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR'] = str(OUT / 'user-data')
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import Window
from fluent_ui import stylesheet
from subtitle_store import SubtitleStore

app = QApplication([])
app.setStyle('Fusion')
app.setStyleSheet(stylesheet(True))
w = Window()
w.audio.setMuted(True)
w.show()
checks = {}

def wait_for(predicate, timeout=25):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(25)
    raise AssertionError('Timed out: ' + repr({'status': w.status.text(), 'frames': w.frames,
        'position': w.player.position(), 'duration': w.player.duration(), 'resume': w.resume_position,
        'state': str(w.player.playbackState()), 'page': w.stack.currentIndex()}))

try:
    wait_for(lambda: bool(w.catalog_model.items))
    w.open_detail({'subjectId': '7334238215282770232', 'subjectType': 1, 'title': 'The Odyssey [Hindi]'})
    wait_for(lambda: bool(w.detail_data))
    assert not w.season.isVisible() and not w.episode_panel.isVisible()
    checks['movie_has_no_seasons'] = True
    wait_for(lambda: bool(w.prepared_media) and w.prepared_media['key'] == w.selection_key() and w.player.isSeekable() and not getattr(w, 'prebuffering', False), 40)
    checks['movie_qualities'] = sorted({int(s['resolutions']) for s in w.stream_cache[w.selection_key()][1]}, reverse=True)
    assert 1080 in checks['movie_qualities']
    w.grab().save(str(OUT / 'movie-detail.png'))
    w.watch_current()
    wait_for(lambda: w.frames > 5, 25)
    checks['prepared_movie_click_to_frame_ms'] = round(w.last_startup_ms or 0)
    w.leave_player()
    w.activateWindow()
    w.raise_()
    QTest.qWait(150)
    w.search.setFocus()
    QTest.keyClicks(w.search, 'Interst')
    wait_for(lambda: w.suggestion_model.rowCount() > 0)
    checks['database_suggestions'] = [w.suggestion_model.item(i).text() for i in range(w.suggestion_model.rowCount())]
    w.completer.popup().hide()
    sample = {'subjectId': '6853990427147001176', 'subjectType': 2, 'title': 'The Rings of Power'}
    key = '6853990427147001176:1:1'
    w.state['history'][key] = {'subject': sample.copy(), 'position': 64000, 'duration': 3947000, 'updated': time.time()}
    w.open_detail(sample)
    wait_for(lambda: bool(w.detail_data))
    assert w.season.isVisible() and w.episode_cards.count() > 0
    checks['series_episode_buttons'] = w.episode_cards.count()
    wait_for(lambda: bool(w.prepared_media) and w.prepared_media['key'] == w.selection_key() and w.player.isSeekable() and not getattr(w, 'prebuffering', False), 40)
    key = w.selection_key()
    w.activateWindow()
    w.raise_()
    w.watch.setFocus()
    QTest.qWait(100)
    QTest.keyClick(w.watch, Qt.Key_Return)
    wait_for(lambda: w.frames > 5 and w.player.position() >= 64000, 35)
    checks['prepared_click_to_frame_ms'] = round(w.last_startup_ms or 0)
    checks['resumed_position_ms'] = w.player.position()
    wait_for(lambda: bool(w.subtitle_track.cues), 25)
    checks['automatic_subtitle_cues'] = len(w.subtitle_track.cues)
    checks['subtitle_selection'] = w.caption_selector.currentText()
    store = SubtitleStore(OUT / 'user-data' / 'subtitles')
    cached = store.prepare(key, 'en', lambda: (_ for _ in ()).throw(AssertionError('Cached replay attempted network discovery')))
    assert cached['cached'] and cached['cues']
    checks['subtitles_replay_without_network'] = True
    w.player.pause()
    QTest.mouseClick(w.progress, Qt.LeftButton, pos=QPoint(int(w.progress.width() * .75), w.progress.height() // 2))
    assert abs(w.player.position() / w.player.duration() - .75) < .025
    checks['click_seek_fraction'] = round(w.player.position() / w.player.duration(), 3)
    w.seek_to(64000)
    w.activateWindow()
    w.raise_()
    QTest.qWait(100)
    QTest.mouseDClick(w.video, Qt.LeftButton)
    QTest.mouseRelease(w.video, Qt.LeftButton)
    wait_for(lambda: bool(w.cinema and w.cinema.isVisible()))
    QTest.qWait(300)
    assert w.cinema.geometry() == w.cinema.screen().geometry()
    assert not w.player_controls.isVisible() and not w.player_header.isVisible()
    assert w.video.caption.isVisible()
    checks['fullscreen_monitor_coverage_and_hidden_controls'] = True
    QTest.mouseMove(w.video, QPoint(150, 170))
    QTest.qWait(100)
    QTest.mouseMove(w.video, QPoint(110, 110))
    wait_for(lambda: w.player_controls.isVisible())
    w.cinema.grab().save(str(OUT / 'fullscreen-controls.png'))
    QTest.qWait(250)
    w.cinema.screen().grabWindow(0).save(str(OUT / 'fullscreen-screen.png'))
    QTest.qWait(2600)
    assert not w.player_controls.isVisible()
    checks['controls_reveal_and_auto_hide'] = True
    QTest.mouseDClick(w.video, Qt.LeftButton, pos=QPoint(200, 150))
    QTest.mouseRelease(w.video, Qt.LeftButton, pos=QPoint(200, 150))
    wait_for(lambda: not w.cinema.isVisible())
    assert w.player_controls.isVisible() and w.player.position() >= 63000
    checks['double_click_exit_preserves_position'] = True
    assert w.quality.width() >= w.quality.fontMetrics().horizontalAdvance('Auto · 1080p') + 45
    checks['quality_text_fits'] = True
    w.save_progress()
    saved = w.state['history'][key]['position']
    w.leave_player()
    wait_for(lambda: bool(w.prepared_media) and not getattr(w, 'prebuffering', False), 25)
    w.watch_current()
    wait_for(lambda: w.frames > 5 and w.player.position() >= saved - 1000, 30)
    checks['replay_resumes'] = True
    checks['replay_click_to_frame_ms'] = round(w.last_startup_ms or 0)
    w.grab().save(str(OUT / 'player.png'))
    if hasattr(w, 'last_frame'):
        w.last_frame.toImage().save(str(OUT / 'decoded-frame.png'))
    w.leave_player()
    w.activateWindow()
    w.episode_cards.setCurrentRow(w.episode_cards.count() - 1)
    w.episode_cards.setFocus()
    chosen = []
    original_watch = w.watch_current
    w.watch_current = lambda: chosen.append(w.episode.currentData())
    QTest.keyClick(w.episode_cards, Qt.Key_Return)
    w.watch_current = original_watch
    assert chosen == [w.episode_cards.currentItem().data(Qt.UserRole)]
    checks['episode_keyboard_enter'] = True
    result = {'passed': True, 'checks': checks}
except Exception as error:
    result = {'passed': False, 'checks': checks, 'error': repr(error), 'traceback': traceback.format_exc()}
finally:
    faulthandler.cancel_dump_traceback_later()
    (OUT / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    w.close()
    app.processEvents()
raise SystemExit(0 if result['passed'] else 1)
