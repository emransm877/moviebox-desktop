"""Offline Qt audit: generated owned video, fake catalogue, isolated app data.

Run with --output DIRECTORY. No upstream service or release assets are used.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import time
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR'] = str(out / 'userdata')

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QUrl, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def fixture_video(path):
    """Create a 40-second MJPEG AVI from an image made here, without downloads."""
    def chunk(tag, data):
        return tag + struct.pack('<I', len(data)) + data + b'\0' * (len(data) % 2)
    def listing(tag, data):
        return chunk(b'LIST', tag + data)
    image = QImage(320, 180, QImage.Format_RGB32)
    image.fill(QColor('#245e89'))
    raw = QByteArray()
    buffer = QBuffer(raw)
    buffer.open(QIODevice.WriteOnly)
    assert image.save(buffer, 'JPEG')
    frame = bytes(raw)
    n, fps = 400, 10
    avih = struct.pack('<14I', 100000, len(frame)*fps, 0, 16, n, 0, 1, len(frame), 320, 180, 0, 0, 0, 0)
    strh = struct.pack('<4s4sIHH8I4h', b'vids', b'MJPG', 0, 0, 0, 0, 1, fps, 0, n, len(frame), 0xffffffff, 0, 0, 0, 320, 180)
    strf = struct.pack('<IiiHH4sIiiII', 40, 320, 180, 1, 24, b'MJPG', 320*180*3, 0, 0, 0, 0)
    header = listing(b'hdrl', chunk(b'avih', avih) + listing(b'strl', chunk(b'strh', strh) + chunk(b'strf', strf)))
    video = b''
    index = b''
    for _ in range(n):
        index += struct.pack('<4sIII', b'00dc', 16, 4+len(video), len(frame))
        video += chunk(b'00dc', frame)
    body = b'AVI ' + header + listing(b'movi', video) + chunk(b'idx1', index)
    path.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)


fixture = out / 'owned-fixture.avi'
fixture_video(fixture)
url = QUrl.fromLocalFile(str(fixture)).toString()
movie = {'subjectId': 'audit-movie', 'subjectType': 1, 'title': 'Owned audit movie'}
series = {'subjectId': 'audit-series', 'subjectType': 2, 'title': 'Owned audit series'}


class API:
    native = None
    account_token = ''
    last_play_info = {}
    def playback(self, subject, season=0, episode=0):
        return [{'url': url, 'id': 'owned', 'resolutions': 720, 'duration': 40, 'size': fixture.stat().st_size},
                {'url': url, 'id': 'owned-480', 'resolutions': 480, 'duration': 40, 'size': fixture.stat().st_size}]
    def captions(self, *a, **kw):
        return {'captions': []}
    def request(self, path, body):
        if 'qr-login-create' in path:
            return {'ticket': 'offline-audit', 'qrUrl': 'https://example.test/offline-audit'}
        return {'items': [movie if body['channelId'] == 1 else series], 'pager': {'hasMore': False}}
    def search(self, query, page=1):
        return {'items': [movie] if page == 1 else [series], 'pager': {'hasMore': page == 1}}
    def suggest(self, query):
        return [{'word': movie['title'], 'subject': movie}]
    def detail(self, subject):
        return {'subject': subject, 'isSeries': subject['subjectType'] == 2,
                'resource': {'seasons': [{'se': 1, 'maxEp': 3}, {'se': 2, 'maxEp': 2}] if subject['subjectType'] == 2 else []}}


import main
from fluent_ui import stylesheet
api = API()
main.MovieBoxService = lambda: api
main.Window.load_home = lambda self: None
main.Window.check_optional_updates = lambda *a, **kw: None
main.Window.maybe_prepare_media = lambda *a: None
app = QApplication([])
app.setStyle('Fusion')
app.setStyleSheet(stylesheet('eclipse'))
w = main.Window()
w.update_timer.stop()
w.adaptive_timer.stop()
w.audio.setMuted(True)
w.show()
checks = {}


def wait(predicate, seconds=6):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not predicate():
        QTest.qWait(30)
    assert predicate(), (w.status.text(), w.player.errorString(), w.frames)


def check(name, action):
    try:
        action()
        checks[name] = {'status': 'PASS'}
    except Exception as error:
        import traceback
        traceback.print_exc()
        checks[name] = {'status': 'FAIL', 'error': repr(error)}
    print(name, checks[name], flush=True)


def expect(value):
    assert value


def start(subject=movie):
    w.stop_media_player()
    w.frames = 0
    w.request_generation += 1
    w.current = subject.copy()
    w.detail_loaded(api.detail(subject), w.request_generation)
    w.watch_current()
    wait(lambda: w.playing_subject and w.playing_subject['subjectId'] == subject['subjectId'] and w.player.isPlaying() and w.frames >= 3)


try:
    def anime_navigation():
        anime = dict(movie, subjectId='audit-anime', title='Owned anime fixture', genre='Animation,Adventure')
        w.sections = {'Offline catalogue': [movie, series, anime]}
        w.nav_buttons['anime'].click()
        expect(w.catalog_model.items == [anime])
        w.catalogue_clicked(w.catalog_model.index(0, 0))
        wait(lambda: w.detail_data is not None and w.current['subjectId'] == 'audit-anime')
        expect(w.stack.currentIndex() == 1)
        w.escape()
        expect(w.stack.currentIndex() == 0 and w.catalog_model.items == [anime])
    check('anime_load_select_back', anime_navigation)
    def hero_controls():
        from PySide6.QtCore import QAbstractAnimation
        w.show_discover();w.resize(1440,940);w.hero.set_slides([movie,series]);scene=w.hero.spatial
        w.poster_delegate.motion=False
        scene.setFocus();QTest.keyClick(scene,Qt.Key_Right)
        expect(w.hero.subject['subjectId']==series['subjectId'])
        QTest.keyClick(scene,Qt.Key_Left);expect(w.hero.subject['subjectId']==movie['subjectId'])
        QTest.keyClick(scene,Qt.Key_Space);expect(w.hero.rotation_paused)
        current=w.hero.slide_index;QTest.qWait(150);expect(w.hero.slide_index==current)
        QTest.keyClick(scene,Qt.Key_Space);expect(not w.hero.rotation_paused)
        w.poster_delegate.motion=True
        # Test automatic navigation with its explicit prerequisites. CI's desktop
        # need not grant foreground focus or enable Windows client-area animation.
        # The separate spatial suite checks the actual SPI reduced-motion guard.
        with patch.object(w,'isActiveWindow',return_value=True), patch.object(scene,'motion_allowed',return_value=True):
            w.activateWindow();w.search.setFocus();scene.last_manual=0;scene.auto.start(80)
            wait(lambda:w.hero.slide_index!=current)
            wait(lambda:scene.animation.state()!=QAbstractAnimation.State.Running)
            scene.setFocus();QTest.keyClick(scene,Qt.Key_Left);current=w.hero.slide_index;scene.auto.start(80);QTest.qWait(150)
            expect(w.hero.slide_index==current)
        selected=w.hero.subject['subjectId'];QTest.keyClick(scene,Qt.Key_Return)
        wait(lambda:w.detail_data is not None and w.current['subjectId']==selected and w.watch.isEnabled() and w.save.isEnabled())
        expect(w.stack.currentIndex()==1 and not w.hero_auto_play)
        saved_before=selected in w.state['saved'];w.save.click();expect((selected in w.state['saved'])!=saved_before)
        w.save.click();expect((selected in w.state['saved'])==saved_before)
        w.watch.click();wait(lambda:w.stack.currentIndex()==2 and w.playing_subject['subjectId']==selected and w.player.isPlaying())
    check('hero_keyboard_pause_auto_own_detail_and_detail_watch_save',hero_controls)
    check('native_owned_video', lambda: start())
    check('video_click_pause', lambda: (QTest.mouseClick(w.video, Qt.LeftButton, pos=w.video.rect().center()), expect(w.player.playbackState() == QMediaPlayer.PausedState)))
    check('video_click_resume', lambda: (QTest.mouseClick(w.video, Qt.LeftButton, pos=w.video.rect().center()), expect(w.player.isPlaying())))
    check('keyboard_space_pause_resume', lambda: (w.video.setFocus(), QTest.keyClick(w.video, Qt.Key_Space), expect(not w.player.isPlaying()), QTest.keyClick(w.video, Qt.Key_Space), expect(w.player.isPlaying())))
    check('seek', lambda: (w.seek_to(12000), wait(lambda: w.player.position() >= 11500)))
    check('quality_keeps_paused_position', lambda: (w.player.pause(), w.quality.setCurrentIndex(2), wait(lambda: w.player.position() >= 11000 and not w.player.isPlaying())))
    check('volume_popover', lambda: (w.mute_button.click(), QTest.qWait(60), expect(w.volume_menu.isVisible()), QTest.keyClick(w.volume, Qt.Key_Escape), expect(not w.volume_menu.isVisible())))
    def volume_inner_controls():
        w.mute_button.click()
        before = w.audio.isMuted()
        w.volume_mute_toggle.click()
        expect(w.audio.isMuted() != before)
        w.volume_mute_toggle.click()
        expect(w.audio.isMuted() == before)
        w.volume.setValue(36)
        expect(abs(w.audio.volume() - .36) < .01 and '36' in w.volume_level.text())
        w.volume.setFocus()
        QTest.keyClick(w.volume, Qt.Key_Right)
        expect(w.audio.volume() > .36)
        QTest.keyClick(w.volume, Qt.Key_Return)
        expect(not w.volume_menu.isVisible())
    check('volume_inner_mute_slider_keyboard', volume_inner_controls)
    def player_row_and_more():
        from PySide6.QtWidgets import QAbstractButton, QComboBox
        row = [w.player_transport_layout.itemAt(i).widget() for i in range(w.player_transport_layout.count())]
        row = [item for item in row if isinstance(item, (QAbstractButton, QComboBox)) and item.isVisible() and item.isEnabled()]
        row[0].setFocus()
        for target in row[1:]:
            QTest.keyClick(app.focusWidget(), Qt.Key_Right)
            expect(app.focusWidget() is target)
        for target in reversed(row[:-1]):
            QTest.keyClick(app.focusWidget(), Qt.Key_Left)
            expect(app.focusWidget() is target)
        w.quality.setFocus()
        QTest.keyClick(w.quality, Qt.Key_Up)
        expect(app.focusWidget() is w.progress)
        QTest.keyClick(w.progress, Qt.Key_Down)
        expect(app.focusWidget() is w.quality)
        w.subtitle_tools.click()
        QTest.qWait(60)
        expect(w.subtitle_tools_menu.isVisible() and w.player_download_action.isEnabled())
        before = w.subtitle_delay.value()
        w.subtitle_delay.setValue(before + 1000)
        expect(w.subtitle_delay.value() == before + 1000)
        w.subtitle_delay.setValue(before)
        QTest.keyClick(w.subtitle_tools_menu, Qt.Key_Escape)
        expect(not w.subtitle_tools_menu.isVisible())
    check('player_row_arrows_seek_return_more_timing', player_row_and_more)
    check('video_fit_cycles', lambda: (w.cycle_video_fit(), w.cycle_video_fit(), w.cycle_video_fit()))
    subtitle = out / 'owned.srt'
    subtitle.write_text('1\n00:00:00,000 --> 00:00:39,000\nOwned audit caption\n', encoding='utf-8')
    with patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(subtitle), '')):
        check('local_subtitle_import', lambda: (w.open_subtitles(), expect(w.subtitle_track.at(12000) == 'Owned audit caption')))
    check('local_subtitle_off_and_reselect', lambda: (expect((w.caption_selector.currentData() or {}).get('lan') == 'local'), w.caption_selector.setCurrentIndex(0), expect(not w.subtitle_track.at(12000)), w.caption_selector.setCurrentIndex(1), expect(w.subtitle_track.at(12000) == 'Owned audit caption')))
    w.player.play()
    check('fullscreen_enter_exit', lambda: (w.toggle_fullscreen(), QTest.qWait(100), expect(w.cinema.isFullScreen()), w.cinema.grab().save(str(out/'fullscreen.png')), w.toggle_fullscreen(), expect(not w.cinema.isVisible())))
    def keep_awake_follows_playback():
        # Real decoder state drives the Windows sleep/display request.
        awake = lambda: w.keep_awake.active
        start()
        wait(awake)
        w.toggle_pause(); wait(lambda: not awake())
        w.toggle_pause(); wait(awake)
        w.toggle_fullscreen(); QTest.qWait(100); expect(w.cinema.isFullScreen() and awake())
        w.toggle_pause(); wait(lambda: not awake())
        w.toggle_pause(); wait(awake)
        w.toggle_fullscreen(); expect(not w.cinema.isVisible() and awake())
        w.leave_player(); wait(lambda: not awake())
        start(); wait(awake)
        w.stop_media_player(); wait(lambda: not awake())
        with patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(fixture), '')):
            w.open_local()
        wait(lambda: w.frames >= 3 and awake())
        w.seek_to(39000); wait(lambda: not awake(), 10)
        start(); wait(awake)
    check('keep_awake_follows_playback', keep_awake_follows_playback)
    QTest.qWait(250)
    w.grab().save(str(out/'player.png'))
    w.video.videoSink().videoFrame().toImage().save(str(out/'decoded-frame.png'))
    region = w.frameGeometry()
    w.screen().grabWindow(0, region.x(), region.y(), region.width(), region.height()).save(str(out/'desktop-player.png'))
    def navigate_playing():
        start()
        before = time.monotonic()
        w.nav_buttons['movies'].click()
        expect(time.monotonic()-before < 1.5)
        wait(lambda: w.catalog_model.items == [movie])
        expect(not w.player.isPlaying())
        start(series)
        before = time.monotonic()
        w.nav_buttons['series'].click()
        expect(time.monotonic()-before < 1.5)
        wait(lambda: w.catalog_model.items == [series])
        expect(not w.player.isPlaying())
    check('movies_tv_navigation_while_playing', navigate_playing)
    w.grab().save(str(out/'tv-catalogue.png'))
    check('catalogue_apply_reset', lambda: (w.apply_catalogue_filters(), QTest.qWait(150), w.reset_catalogue_filters(), QTest.qWait(150), expect(w.catalogue_kind == 'series')))
    def catalogue_search_failure_recovery():
        w.catalogue_cache.entries.clear()
        with patch.object(api, 'request', side_effect=OSError('Owned catalogue outage')):
            w.browse_catalogue('movies')
            wait(lambda: 'could not load' in w.empty.text())
            expect(w.catalogue_apply.isEnabled() and w.catalogue_reset.isEnabled())
        w.catalogue_apply.click()
        wait(lambda: w.catalog_model.items == [movie])
        with patch.object(api, 'search', side_effect=OSError('Owned search outage')):
            w.search.setText('failed fixture')
            w.run_search()
            wait(lambda: 'Owned search outage' in w.status.text())
        w.run_search()
        wait(lambda: w.catalog_model.items == [movie])
    check('catalogue_search_network_failure_retry', catalogue_search_failure_recovery)
    def search():
        w.search.setText('Owned')
        w.run_search()
        wait(lambda: w.catalog_model.items == [movie])
        w.load_more()
        wait(lambda: len(w.catalog_model.items) == 2)
        w.search.setFocus()
        w.request_suggestions()
        wait(lambda: w.suggestion_model.rowCount() == 1)
        w.accept_suggestion(w.suggestion_model.index(0, 0))
        wait(lambda: w.stack.currentIndex() == 1)
    check('search_pagination_suggestions', search)
    def episodes():
        start(series)
        w.open_player_episodes()
        expect(w.player_episode_panel.isVisible())
        w.player_season_picker.setCurrentIndex(1)
        expect(w.player.isPlaying())
        w.play_player_episode(w.player_episode_list.item(1))
        wait(lambda: w.playing_key == 'audit-series:2:2' and w.player.isPlaying())
    check('episode_drawer_exact_selection', episodes)
    def episode_end():
        w.media_status(QMediaPlayer.EndOfMedia)
        wait(lambda: w.stack.currentIndex() == 1)
        expect(not w.player.isPlaying())
        start(series)
        w.season.setCurrentIndex(0)
        w.episode.setCurrentIndex(0)
        w.watch_current()
        wait(lambda: w.playing_key == 'audit-series:1:1' and w.player.isPlaying())
        w.media_status(QMediaPlayer.EndOfMedia)
        wait(lambda: w.playing_key == 'audit-series:1:2' and w.player.isPlaying())
    check('series_end_and_auto_next', episode_end)
    def next_up_controls():
        from PySide6.QtWidgets import QPushButton
        start(series)
        w.season.setCurrentIndex(0)
        w.episode.setCurrentIndex(0)
        w.watch_current()
        wait(lambda: w.playing_key == 'audit-series:1:1' and w.player.isPlaying())
        w.position_changed(w.player.duration() - 1000)
        expect(w.next_up_panel.isVisible())
        next(button for button in w.next_up_panel.findChildren(QPushButton) if button.text() == 'Hide').click()
        expect(not w.next_up_panel.isVisible() and w.player.isPlaying())
        w.next_up_dismissed_key = ''
        w.position_changed(w.player.duration() - 1000)
        next(button for button in w.next_up_panel.findChildren(QPushButton) if button.text() == 'Play next').click()
        wait(lambda: w.playing_key == 'audit-series:1:2' and w.player.isPlaying())
    check('next_up_hide_and_play_next_buttons', next_up_controls)
    check('saved_add_remove', lambda: (w.toggle_saved(), expect('audit-series' in w.state['saved']), w.show_saved(), expect(len(w.catalog_model.items) == 1), w.toggle_saved(), expect(not w.state['saved'])))
    def history():
        start()
        w.seek_to(15000)
        wait(lambda: w.player.position() >= 14500)
        w.show_history()
        expect('audit-movie:0:0' in w.state['history'])
        w.begin_history_selection()
        w.select_all_history()
        w.remove_selected_history()
        expect(not w.state['history'])
        w.undo_history_removal()
        expect('audit-movie:0:0' in w.state['history'])
    check('history_remove_undo', history)
    def signed_download():
        start()
        w.current_stream.update({'signHeaderKey': 'X-Owned-Signature', 'signCookie': 'offline-only'})
        with patch.object(main.QFileDialog, 'getSaveFileName', return_value=(str(out/'download-fixture.mp4'), '')), patch.object(w.download_pool, 'submit') as submit:
            w.download_current()
            expect(w.downloads[-1].headers['X-Owned-Signature'] == 'offline-only')
            expect(submit.call_count == 1)
        w.downloads.clear()
    check('signed_download_header_parity', signed_download)
    def audio_edition():
        subject = dict(movie, dubs=[{'type': 0, 'subjectId': 'audit-dub', 'lanCode': 'bn', 'lanName': 'Bangla'}])
        start(subject)
        w.seek_to(18000)
        wait(lambda: w.player.position() >= 17500)
        w.player.pause()
        option = next(row for row in range(w.audio_tracks.count()) if (w.audio_tracks.itemData(row) or {}).get('kind') == 'edition')
        w.audio_tracks.setCurrentIndex(option)
        wait(lambda: w.playing_key == 'audit-dub:0:0' and not w.player.isPlaying() and w.player.position() >= 17500)
        expect(w.state['audio_preferences']['audit-movie']['subjectId'] == 'audit-dub')
        w.state['audio_preferences'].clear()
        w.persist()
    check('audio_edition_preserves_paused_position', audio_edition)
    def adaptive_quality_changes():
        start()
        w.streams = [dict(w.streams[0], size=30_000_000), dict(w.streams[1], size=1_000_000)]
        w.current_stream = w.streams[0]
        w.quality.blockSignals(True)
        w.quality.setCurrentIndex(0)
        w.quality.blockSignals(False)
        w.auto_bandwidth = 0
        def probe(speed):
            w.last_auto_probe = 0
            w.seek_grace_until = 0
            with patch.object(main, 'measure_mbps', return_value=speed):
                w.adapt_quality()
                wait(lambda: not w.auto_probe_running)
        probe(.3)
        wait(lambda: w.current_stream['resolutions'] == 480 and w.player.isPlaying())
        probe(100)
        expect(w.current_stream['resolutions'] == 480)
        probe(100)
        wait(lambda: w.current_stream['resolutions'] == 720 and w.player.isPlaying())
        expect('720p' in w.quality.itemText(0))
    check('adaptive_quality_bandwidth_drop_upgrade_hysteresis', adaptive_quality_changes)
    def audio_cut_menu():
        subject = dict(movie, dubs=[{'type': 0, 'subjectId': 'audit-cut', 'lanCode': 'bn', 'lanName': 'Bangla'}])
        start(subject)
        w.seek_to(10000)
        wait(lambda: w.player.position() >= 9500)
        w.player.pause()
        original = api.playback
        def cut_streams(target, *args):
            streams = original(target, *args)
            return [dict(stream, duration=55) for stream in streams] if target['subjectId'] == 'audit-cut' else streams
        with patch.object(api, 'playback', side_effect=cut_streams):
            option = next(row for row in range(w.audio_tracks.count()) if (w.audio_tracks.itemData(row) or {}).get('kind') == 'edition')
            w.audio_tracks.setCurrentIndex(option)
            wait(lambda: hasattr(w, 'audio_cut_menu') and w.audio_cut_menu.isVisible())
            expect(w.playing_key == 'audit-movie:0:0' and w.player.position() >= 9500)
            next(action for action in w.audio_cut_menu.actions() if action.text() == 'Keep current audio').trigger()
            w.audio_cut_menu.hide()
            expect(w.playing_key == 'audit-movie:0:0' and not w.player.isPlaying())
            option = next(row for row in range(w.audio_tracks.count()) if (w.audio_tracks.itemData(row) or {}).get('kind') == 'edition')
            w.audio_tracks.setCurrentIndex(option)
            wait(lambda: w.audio_cut_menu.isVisible())
            next(action for action in w.audio_cut_menu.actions() if action.text().startswith('Restart in ')).trigger()
            w.audio_cut_menu.hide()
            wait(lambda: w.playing_key == 'audit-cut:0:0' and not w.player.isPlaying() and w.player.position() < 2000)
            expect(w.state['audio_preferences']['audit-movie']['restart_for_cut'])
        w.state['audio_preferences'].clear()
        w.persist()
    check('audio_different_cut_keep_and_restart', audio_cut_menu)
    def caption_failure_retry():
        import io
        descriptor = {'id': 'retry-en', 'lan': 'en', 'lanName': 'English retry', 'url': 'https://example.test/owned.srt'}
        with patch.object(api, 'captions', return_value={'captions': [descriptor]}):
            with patch('subtitle_store.urlopen', side_effect=OSError('offline fixture failure')):
                start(dict(movie, subjectId='audit-caption-retry'))
                wait(lambda: w.caption_selector.count() == 2 and 'failed' in w.caption_selector.toolTip().lower())
                expect(not w.subtitle_track.cues)
            payload = b'1\n00:00:00,000 --> 00:00:39,000\nRecovered owned subtitle\n'
            with patch('subtitle_store.urlopen', side_effect=lambda *a, **kw: io.BytesIO(payload)):
                w.caption_selector.setCurrentIndex(1)
                wait(lambda: w.subtitle_track.at(1000) == 'Recovered owned subtitle')
    check('subtitle_failure_language_picker_retry', caption_failure_retry)
    def dialog_cancellation():
        start()
        before = (w.player.source(), w.playing_key, len(w.downloads), list(w.subtitle_track.cues))
        with patch.object(main.QFileDialog, 'getOpenFileName', return_value=('', '')):
            w.open_local()
            w.open_subtitles()
        with patch.object(main.QFileDialog, 'getSaveFileName', return_value=('', '')):
            w.download_current()
        expect((w.player.source(), w.playing_key, len(w.downloads), list(w.subtitle_track.cues)) == before)
    check('open_save_subtitle_dialog_cancellation', dialog_cancellation)
    def local_return():
        with patch.object(main.QFileDialog, 'getOpenFileName', return_value=(str(fixture), '')):
            w.open_local()
        wait(lambda: w.frames >= 3)
        w.leave_player()
        expect(w.stack.currentIndex() == 0)
    check('local_video_back_destination', local_return)
    def downloads_return():
        from PySide6.QtWidgets import QListWidgetItem
        w.show_downloads()
        item = QListWidgetItem('owned')
        item.setData(Qt.UserRole, str(fixture))
        w.open_download(item)
        wait(lambda: w.frames >= 3)
        w.leave_player()
        expect(w.stack.currentIndex() == 3)
    check('download_video_back_destination', downloads_return)
    def trailer():
        subject = dict(movie, trailer={'videoAddress': {'url': url}})
        w.current = subject
        w.detail_loaded(api.detail(subject), w.request_generation)
        expect(w.trailer.isEnabled())
        w.trailer.click()
        wait(lambda: w.frames >= 3 and w.player.isPlaying())
        expect(w.playing_subject is None and not w.download_button.isEnabled())
        w.leave_player()
        expect(w.stack.currentIndex() == 1)
    check('trailer_button_local_source_and_back', trailer)
    def updates():
        import release_updates
        notice = release_updates.UpdateNotice('99.0.0', 'https://github.com/emransm877/moviebox-desktop/releases/tag/v99.0.0', 'https://github.com/emransm877/moviebox-desktop/releases/download/v99.0.0/MovieBox-Setup-99.0.0-windows-x64.exe', 'MovieBox-Setup-99.0.0-windows-x64.exe', 100)
        w.update_notice = notice
        w.state['update_notifications']['enabled'] = True
        w.stack.setCurrentIndex(2)
        w.present_optional_update()
        expect(not w.update_banner.isVisible())
        w.stack.setCurrentIndex(0)
        expect(w.update_banner.isVisible())
        with patch.object(main.QDesktopServices, 'openUrl', return_value=True) as opened:
            w.download_optional_update()
            expect(opened.call_args.args[0].toString() == notice.download_url)
        w.update_notice = notice
        w.skip_optional_update()
        expect(w.state['update_notifications']['skipped_version'] == '99.0.0')
        w.state['update_notifications']['skipped_version'] = ''
        w.update_notice = notice
        w.present_optional_update()
        from PySide6.QtWidgets import QPushButton
        next(button for button in w.update_banner.findChildren(QPushButton) if button.text() == 'Later').click()
        expect(w.update_notice is None and not w.update_banner.isVisible())
        w.configure_optional_updates(False)
        expect(not w.state['update_notifications']['enabled'])
    check('update_defer_link_skip_optout', updates)
    def settings():
        from fluent_ui import open_settings
        from PySide6.QtWidgets import QComboBox, QSpinBox, QPushButton
        def interact():
            dialog = app.activeModalWidget()
            dialog.findChild(QPushButton, 'themeOption-orbital').click()
            dialog.findChild(QComboBox, 'appearancePicker').setCurrentIndex(2)
            dialog.findChild(QSpinBox, 'subtitleSize').setValue(30)
            dialog.grab().save(str(out/'settings.png'))
            dialog.accept()
        QTimer.singleShot(150, interact)
        open_settings(w)
        expect(w.state['appearance'] == 'light' and w.state['subtitle_size'] == 30)
    check('settings_theme_appearance_subtitle_size', settings)
    def account_cancel():
        from account import LoginDialog
        dialog = LoginDialog(w)
        dialog.show()
        wait(lambda: dialog.ticket == 'offline-audit')
        expect(not dialog.qr.pixmap().isNull())
        dialog.grab().save(str(out/'account-stub.png'))
        dialog.reject()
        expect(not dialog.timer.isActive())
    check('account_qr_stub_cancel', account_cancel)
    def synthetic_signout():
        from PySide6.QtWidgets import QMessageBox
        token = 'synthetic-local-audit-token-invalid-upstream'
        w.store_account(token)
        expect(w.sign_in.text() == 'Account' and (main.DATA/'session.bin').is_file())
        def answer(choice):
            dialog = app.activeModalWidget()
            expect(isinstance(dialog, QMessageBox))
            dialog.button(choice).click()
        QTimer.singleShot(80, lambda: answer(QMessageBox.No))
        w.open_account()
        expect(api.account_token == token and (main.DATA/'session.bin').is_file())
        QTimer.singleShot(80, lambda: answer(QMessageBox.Yes))
        w.open_account()
        expect(not api.account_token and not (main.DATA/'session.bin').exists() and w.sign_in.text() == 'Sign in')
    check('synthetic_signed_in_signout_no_yes', synthetic_signout)
    def system_appearance_event():
        from fluent_ui import refresh_theme
        w.state['appearance'] = 'system'
        w.state['theme'] = 'obsidian'
        refresh_theme(w, 'obsidian')
        app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
        QTest.qWait(30)
        expect(w.state['theme'] == 'aurora' and not app.property('movieboxDark'))
        app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        QTest.qWait(30)
        expect(w.state['theme'] == 'obsidian' and app.property('movieboxDark'))
        w.state['appearance'] = 'theme'
        app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
        QTest.qWait(30)
        expect(w.state['theme'] == 'obsidian')
    check('follow_windows_color_scheme_events', system_appearance_event)
    def restricted_controls():
        w.stop_media_player()
        w.stack.setCurrentIndex(1)
        subject = dict(movie, accessStrategy={'requiredVipLevel': 1, 'freeEpisodeCount': 0, 'previewSeconds': 0})
        w.current = subject
        w.detail_loaded(api.detail(subject), w.request_generation)
        w.watch_current()
        expect(w.stack.currentIndex() == 1 and 'membership' in w.status.text())
        subject['accessStrategy']['previewSeconds'] = 3
        w.watch_current()
        wait(lambda: w.player.isPlaying())
        expect(w.preview_limit == 3000 and not w.download_button.isEnabled())
        w.position_changed(3500)
        expect(not w.player.isPlaying() and 'preview ended' in w.status.text())
        w.seek_to(10000)
        expect(w.player.position() <= 3000)
        api.last_play_info = {'streams': [{'vipLocked': True, 'resolutions': 2160}]}
        start()
        locked = next(index for index in range(w.quality.count()) if 'account required' in w.quality.itemText(index))
        expect(not w.quality.model().item(locked).isEnabled())
        api.last_play_info = {}
    check('membership_preview_end_seek_download_and_locked_quality', restricted_controls)
    def stalled_navigation():
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        entered, release = threading.Event(), threading.Event()
        class Origin(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass
            def do_GET(self):
                entered.set()
                release.wait(20)
                self.send_response(200)
                self.send_header('Content-Type', 'video/x-msvideo')
                self.send_header('Content-Length', str(fixture.stat().st_size))
                self.end_headers()
                self.wfile.flush()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            w.playing_subject, w.playing_key = movie, 'audit-stalled:0:0'
            remote = f'http://127.0.0.1:{server.server_port}/owned-stalled.avi'
            w.current_stream = {'url': remote, 'id': 'owned-stalled', 'duration': 40, 'resolutions': 720}
            w.start_video(remote)
            wait(lambda: entered.is_set())
            before = time.monotonic()
            w.nav_buttons['movies'].click()
            elapsed = time.monotonic() - before
            checks['stalled_navigation_timing'] = {'status': 'PASS' if elapsed < 1.5 else 'FAIL', 'seconds': elapsed}
            expect(elapsed < 1.5)
            wait(lambda: w.catalog_model.items == [movie])
        finally:
            release.set()
            server.shutdown()
            server.server_close()
    check('stalled_loopback_navigation', stalled_navigation)
    check('library_disk_snapshot', lambda: expect('audit-movie:0:0' in main.LibraryStore(main.STATE_PATH).load()['history']))
finally:
    awake_before_close = w.keep_awake.active
    w.close()
    app.processEvents()
    checks['keep_awake_released_on_close'] = {'status': 'PASS' if not w.keep_awake.active else 'FAIL', 'active_before_close': awake_before_close}
    (out/'results.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')

raise SystemExit(1 if any(v['status'] == 'FAIL' for v in checks.values()) else 0)
