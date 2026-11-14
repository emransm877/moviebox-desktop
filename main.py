from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import Future
from urllib.request import Request, urlopen

from PySide6.QtCore import (Qt, QAbstractListModel, QModelIndex, QSize, QObject, QPoint, QRectF, QEvent, QVariantAnimation, QEasingCurve,
                            Signal, QRunnable, QThreadPool, QTimer, QUrl, QStandardPaths, QBuffer, QByteArray, QIODevice)
from PySide6.QtGui import QColor, QPainter, QPixmap, QFont, QShortcut, QKeySequence, QIcon, QImageReader, QStandardItemModel, QStandardItem, QDesktopServices, QPen
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QStackedWidget,
    QListView, QStyledItemDelegate, QSlider, QFrame, QMessageBox, QFileDialog, QStyle, QSpinBox, QListWidget, QListWidgetItem, QSizePolicy, QCheckBox, QCompleter)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoFrame, QMediaMetaData
from PySide6.QtMultimediaWidgets import QVideoWidget
from shiboken6 import isValid
from service import MovieBoxService, ServiceError, SITE
from playback import Subtitles, fetch_subtitles, parse_subtitles, measure_mbps, select_quality
from media_bridge import MediaBridge
from downloads import Download
from secure_storage import transform as protect_session
from subtitle_store import SubtitleStore
from interactions import InputRouter, CinemaWindow
from audio_options import audio_variants, language_label, with_audio, matching_runtime, full_runtime_streams
from library_store import LibraryStore
import release_updates
from artwork import resized_artwork
from catalogue_cache import CatalogueCache, compact as compact_catalogue_subject
from series_policy import next_episode as following_episode, next_up_at, episode_numbers

APP_VERSION = '0.10.2'


DATA = Path(os.environ['MOVIEBOX_DATA_DIR']) if os.environ.get('MOVIEBOX_DATA_DIR') else Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'MovieBoxDesktop'
CACHE = DATA / 'artwork'
CACHE.mkdir(parents=True, exist_ok=True)
STATE_PATH = DATA / 'library.json'


def load_state():
    return LibraryStore(STATE_PATH).load()


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn, self.signals = fn, Signals()

    def run(self):
        try:
            result = self.fn()
        except Exception as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.done.emit(result)


class Artwork(QObject):
    changed = Signal()

    def __init__(self, pool):
        super().__init__()
        self.pool, self.images, self.pending, self.failed = pool, OrderedDict(), set(), set()
        self.tasks = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(40)

    def get(self, url):
        if not url:
            return None
        if url in self.images:
            self.images.move_to_end(url)
            return self.images[url]
        if url in self.pending or url in self.failed or len(self.pending) >= 12:
            return None
        self.pending.add(url)
        self.tasks[self.pool.submit(self.fetch_image, url)] = url
        return None

    def poll(self):
        for future, url in list(self.tasks.items()):
            if not future.done():
                continue
            del self.tasks[future]
            try:
                data = future.result()
            except Exception:
                self.error(url)
            else:
                self.ready(url, data)

    @staticmethod
    def fetch(url, width=960):
        url = resized_artwork(url, width)
        path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.img')
        if path.exists():
            return path.read_bytes()
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=12) as response:
            data = response.read(8 * 1024 * 1024)
        path.write_bytes(data)
        return data

    @staticmethod
    def fetch_image(url):
        data = Artwork.fetch(url, 360)
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.ReadOnly)
        reader = QImageReader(buffer)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            size.scale(QSize(360, 540), Qt.KeepAspectRatio)
            reader.setScaledSize(size)
        return reader.read()

    def ready(self, url, decoded):
        self.pending.discard(url)
        if not decoded.isNull():
            self.images[url] = QPixmap.fromImage(decoded)
            while len(self.images) > 100:
                self.images.popitem(last=False)
        else:
            self.failed.add(url)
        self.changed.emit()

    def error(self, url):
        self.pending.discard(url)
        self.failed.add(url)
        self.changed.emit()


class CatalogModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.items = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.items):
            return None
        if role == Qt.UserRole:
            return self.items[index.row()]
        if role in (Qt.DisplayRole, Qt.AccessibleTextRole, Qt.ToolTipRole):
            return self.items[index.row()].get('title', '')

    def replace(self, items):
        self.beginResetModel()
        seen = set()
        self.items = []
        for item in items:
            key = item.get('subjectId')
            if key and key not in seen:
                seen.add(key)
                self.items.append(item)
        self.endResetModel()


class PosterDelegate(QStyledItemDelegate):
    def __init__(self, artwork, parent):
        super().__init__(parent)
        self.artwork = artwork
        self.view = parent
        self.viewport = parent.viewport()
        self.hover_row = -1
        self.active_row = -1
        self.amounts = {}
        self.starts = {}
        self.metrics = {'frames': 0, 'maxActiveRows': 0, 'maxFrameMs': 0}
        self.motion = True
        if os.name == 'nt':
            try:
                import ctypes
                enabled = ctypes.c_int(1)
                if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
                    self.motion = bool(enabled.value)
            except (AttributeError, OSError):
                pass
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(160)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.animate_frame)
        self.viewport.setMouseTracking(True)
        self.viewport.installEventFilter(self)
        parent.installEventFilter(self)
        parent.selectionModel().currentChanged.connect(self.current_changed)
        parent.model().modelAboutToBeReset.connect(self.clear_focus)

    def eventFilter(self, watched, event):
        if not isValid(self.view) or not isValid(self.viewport):
            return False
        if watched is self.viewport:
            if event.type() == QEvent.MouseMove:
                index = self.view.indexAt(event.position().toPoint())
                self.hover_row = index.row() if index.isValid() else -1
                self.update_active()
            elif event.type() == QEvent.Leave:
                self.hover_row = -1
                self.update_active()
        if watched is self.view:
            if event.type() in (QEvent.FocusIn, QEvent.FocusOut):
                if event.type() == QEvent.FocusIn:
                    self.hover_row = -1
                self.update_active()
            elif event.type() == QEvent.Hide:
                self.clear_focus()
        return False

    def current_changed(self, *_):
        if isValid(self.view) and self.view.hasFocus():
            self.hover_row = -1
        self.update_active()

    def update_active(self):
        if not isValid(self.view):
            return
        current = self.view.currentIndex()
        target = self.hover_row if self.hover_row >= 0 else current.row() if self.view.hasFocus() and current.isValid() else -1
        if target == self.active_row:
            return
        old_rows = set(self.amounts)
        previous = self.active_row
        self.animation.stop()
        self.active_row = target
        self.starts = {row: self.amounts.get(row, 0.0) for row in (previous, target) if row >= 0}
        self.amounts = dict(self.starts)
        self.repaint_rows(old_rows | set(self.starts))
        if self.motion:
            self.animation.start()
        else:
            self.animate_frame(1.0)

    def animate_frame(self, fraction):
        started = time.perf_counter()
        rows = set(self.amounts) | set(self.starts)
        self.amounts = {row: initial + (1.0 - initial) * fraction if row == self.active_row else initial * (1.0 - fraction)
                        for row, initial in self.starts.items()}
        self.amounts = {row: amount for row, amount in self.amounts.items() if amount > .001}
        self.metrics['frames'] += 1
        self.metrics['maxActiveRows'] = max(self.metrics['maxActiveRows'], len(self.amounts))
        self.repaint_rows(rows)
        self.metrics['maxFrameMs'] = max(self.metrics['maxFrameMs'], (time.perf_counter() - started) * 1000)

    def repaint_rows(self, rows):
        if not isValid(self.view) or not isValid(self.viewport):
            return
        model = self.view.model()
        if model is None:
            return
        for row in rows:
            index = model.index(row, 0)
            if index.isValid():
                self.viewport.update(self.view.visualRect(index))

    def clear_focus(self):
        self.animation.stop()
        rows = set(self.amounts)
        self.hover_row = self.active_row = -1
        self.amounts = {}
        self.starts = {}
        self.repaint_rows(rows)

    @staticmethod
    def cover_rect(cell, amount=0):
        rect = QRectF(cell.adjusted(6, 6, -6, -6))
        cover = rect.adjusted(0, 0, 0, -66)
        horizontal, vertical = cover.width() * .0225 * amount, cover.height() * .0225 * amount
        return cover.adjusted(-horizontal, -vertical, horizontal, vertical)

    def sizeHint(self, option, index):
        return QSize(184, 316)

    def paint(self, painter, option, index):
        item = index.data(Qt.UserRole) or {}
        dark = bool(QApplication.instance().property('movieboxDark'))
        painter.save()
        painter.setClipRect(option.rect, Qt.IntersectClip)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(6, 6, -6, -6)
        base_cover = self.cover_rect(option.rect)
        amount = self.amounts.get(index.row(), 0.0)
        cover = self.cover_rect(option.rect, amount)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#1a222d' if dark else '#e5ebf2'))
        painter.drawRoundedRect(cover, 12, 12)
        image = self.artwork.get((item.get('cover') or {}).get('url', ''))
        if image:
            from PySide6.QtGui import QPainterPath
            clip = QPainterPath()
            clip.addRoundedRect(cover, 12, 12)
            painter.save()
            painter.setClipPath(clip)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            scale = max(cover.width() / image.width(), cover.height() / image.height())
            width, height = cover.width() / scale, cover.height() / scale
            source = QRectF((image.width() - width) / 2, (image.height() - height) / 2, width, height)
            painter.drawPixmap(cover, image, source)
            painter.restore()
        painter.setPen(QColor('#f1f5fb' if dark else '#182431'))
        painter.setFont(QFont('Segoe UI Variable Text', 10, QFont.DemiBold))
        title_rect = rect.adjusted(0, int(base_cover.height()) + 10, 0, -22)
        title = painter.fontMetrics().elidedText(item.get('title', ''), Qt.ElideRight, rect.width())
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignTop, title)
        painter.setPen(QColor('#91a0b4' if dark else '#647286'))
        painter.setFont(QFont('Segoe UI Variable Text', 9))
        year = str(item.get('releaseDate') or '')[:4]
        rating = item.get('imdbRatingValue')
        painter.drawText(rect.adjusted(0, rect.height() - 22, 0, 0), Qt.AlignLeft | Qt.AlignVCenter,
                         year + (f'     ★ {rating}' if rating else ''))
        highlighted = bool(option.state & (QStyle.State_MouseOver | QStyle.State_Selected | QStyle.State_HasFocus))
        if highlighted or amount > 0:
            painter.setBrush(Qt.NoBrush)
            if amount > 0:
                halo = QColor(QApplication.instance().property('movieboxAccent') or '#48e6b0')
                halo.setAlpha(round(38 * amount))
                painter.setPen(QPen(halo, 5))
                painter.drawRoundedRect(cover, 12, 12)
            accent = QColor(QApplication.instance().property('movieboxAccent') or '#48e6b0')
            accent.setAlpha(round((150 if highlighted else 0) + (105 if highlighted else 255) * amount))
            painter.setPen(QPen(accent, 1.0 + amount))
            painter.drawRoundedRect(cover, 12, 12)
        if getattr(self.view.window(),'history_editing',False):
            box=QRectF(cover.right()-29,cover.top()+9,21,21)
            selected=bool(option.state & QStyle.State_Selected)
            tone=QColor(QApplication.instance().property('movieboxAccent') or '#48e6b0')
            painter.setPen(QPen(tone,2));painter.setBrush(tone if selected else QColor('#151e28'))
            painter.drawRoundedRect(box,5,5)
            if selected:
                painter.setPen(QColor('#102018' if dark else '#ffffff'));painter.drawText(box,Qt.AlignCenter,'✓')
        painter.restore()


class VideoSurface(QVideoWidget):
    doubleClicked = Signal()

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.caption = QLabel('', self, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.caption.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.caption.setAttribute(Qt.WA_TranslucentBackground, True)
        self.caption.setTextFormat(Qt.PlainText)
        self.caption.setAlignment(Qt.AlignCenter)
        self.caption.setWordWrap(True)
        self.caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.caption.setStyleSheet('background:rgba(0,0,0,180);color:white;font-size:24px;font-weight:600;padding:8px;border-radius:7px')
        self.caption.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_caption()
        stage = getattr(self, 'cinema_stage', None)
        if stage and stage.isVisible():
            stage.position_overlays()

    def position_caption(self):
        stage = getattr(self, 'cinema_stage', None)
        bottom = 115
        if stage and stage.isVisible():
            bottom = stage.owner.player_controls.height() + 130 if stage.controls_visible else 115
        origin = self.mapToGlobal(QPoint(0, 0))
        self.caption.setGeometry(origin.x() + 35, origin.y() + max(0, self.height() - bottom), max(100, self.width() - 70), 90)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
        super().mousePressEvent(event)

    def hideEvent(self, event):
        self.caption.hide()
        super().hideEvent(event)

    def set_caption(self, text):
        if self.caption.text() != text:
            self.caption.setText(text)
        self.caption.setVisible(bool(text) and self.isVisible())
        self.caption.raise_()


def button(text, fn=None, *, primary=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.PointingHandCursor)
    if primary:
        widget.setObjectName('primary')
    if fn:
        widget.clicked.connect(fn)
    return widget


def timestamp(milliseconds):
    seconds = max(0, int(milliseconds) // 1000)
    return f'{seconds // 3600}:{seconds // 60 % 60:02}:{seconds % 60:02}'


class Window(QMainWindow):
    catalog_ready = Signal()
    detail_ready = Signal()
    playback_ready = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('MovieBox Desktop · Preview')
        self.resize(1320, 860)
        self.setMinimumSize(950, 650)
        self.api = MovieBoxService()
        try:
            self.api.account_token = protect_session((DATA / 'session.bin').read_bytes(), decrypt=True).decode()
        except (OSError, ValueError, UnicodeError):
            pass
        self.bridge = MediaBridge()
        self.library_store = LibraryStore(STATE_PATH)
        self.state = self.library_store.load()
        self.last_progress_checkpoint = None
        if not self.state.get('subtitle_auto_cache_version'):
            self.state['subtitle_enabled'] = True
            self.state['subtitle_language'] = self.state.get('subtitle_language') or 'en'
            self.state['subtitle_auto_cache_version'] = 1
        self.subtitle_store = SubtitleStore(DATA / 'subtitles')
        self.stream_requests, self.stream_cache, self.caption_requests = {}, {}, {}
        self.prepared_media = None
        self.cinema = None
        self.last_startup_ms = None
        self.play_intent = 0
        self.audio_switch_intent = 0
        self.audio_switching = False
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='moviebox-api')
        self.art_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='moviebox-art')
        self.art = Artwork(self.art_pool)
        self.jobs = {}
        self.job_timer = QTimer(self)
        self.job_timer.timeout.connect(self.poll_jobs)
        self.job_timer.start(40)
        self.sections, self.current, self.detail_data = {}, None, None
        self.streams, self.playing_subject = [], None
        self.request_generation = 0
        self.search_page, self.search_keyword = 1, ''
        self.playing_key, self.resume_position, self.preview_limit = '', 0, 0
        self.frames = 0
        self.subtitle_track = Subtitles()
        self.subtitle_generation = 0
        self.current_stream = None
        self.auto_bandwidth, self.last_auto_probe = 0, 0
        self.auto_probe_running = False
        self.auto_candidate, self.auto_votes = '', 0
        self.downloads = []
        self.catalogue_kind = None
        self.catalogue_page = 1
        self.catalogue_next_page = 2
        self.catalogue_cache = CatalogueCache(DATA / 'catalogue-cache.json')
        self.active_catalogue_cache_key = ''
        self.catalogue_pending_refresh_key = ''
        self.history_editing = False
        self.history_undo = {}
        self.end_handled = False
        self.playback_return_view = None
        self.continuation_starting = False
        self.next_up_dismissed_key = ''
        self.video_click_time = 0
        self.video_click_state = None
        self.suppress_video_release = False
        self.catalogue_selections = self.state.get('catalogue_filters', {})
        if not isinstance(self.catalogue_selections, dict):
            self.catalogue_selections = {}
        self.catalogue_backend = None
        self.download_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='moviebox-download')
        self.build_ui()
        self.build_player()
        self.setup_optional_updates()
        self.input_router = InputRouter(self)
        self.video.doubleClicked.connect(self.video_double_click)
        self.setup_suggestions()
        self.autosave = QTimer(self)
        self.autosave.timeout.connect(self.save_progress)
        self.autosave.start(1000)
        self.adaptive_timer = QTimer(self)
        self.adaptive_timer.timeout.connect(self.adapt_quality)
        self.adaptive_timer.start(15000)
        self.download_timer = QTimer(self)
        self.download_timer.timeout.connect(self.update_downloads)
        self.download_timer.start(500)
        QTimer.singleShot(0, self.load_home)
        if self.api.native:
            self.submit(self.api.native.warm_up, lambda result: None, message='', failure=lambda message: None)

    def setup_optional_updates(self):
        self.update_notice = None
        self.update_inflight = False
        self.update_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='moviebox-updates')
        self.state.setdefault('update_notifications', {'enabled': True, 'last_checked': 0, 'skipped_version': ''})
        self.update_banner = QFrame()
        self.update_banner.setObjectName('controlBar')
        row = QHBoxLayout(self.update_banner)
        self.update_label = QLabel()
        self.update_label.setWordWrap(True)
        row.addWidget(self.update_label, 1)
        for label, callback in [('Download update', self.download_optional_update), ('Later', self.dismiss_optional_update), ('Skip this version', self.skip_optional_update)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        self.content_layout.insertWidget(0, self.update_banner)
        self.update_banner.hide()
        self.stack.currentChanged.connect(self.present_optional_update)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_optional_updates)
        self.update_timer.start(60000)
        QTimer.singleShot(12000, self.check_optional_updates)

    def check_optional_updates(self, force=False):
        settings = self.state['update_notifications']
        self.present_optional_update()
        if self.update_inflight or not release_updates.check_due(settings, force=force):
            return
        self.update_inflight = True
        future = self.update_pool.submit(release_updates.check_for_update, APP_VERSION, dict(settings), force=force)
        def ready(result):
            self.update_inflight = False
            self.state['update_notifications'] = release_updates.record_result(self.state['update_notifications'], result)
            self.persist()
            self.update_notice = result.notice
            self.present_optional_update()
            if force and not result.notice:
                self.status.setText('Update check unavailable. Try again later.' if result.error else 'No newer unskipped MovieBox release is available.')
        def fail(_):
            self.update_inflight = False
        self.await_future(future, ready, fail)

    def present_optional_update(self, *_):
        allowed = release_updates.notice_is_allowed(self.state['update_notifications'], self.update_notice)
        show = allowed and self.stack.currentIndex() != 2 and not (self.cinema and self.cinema.isVisible())
        self.update_banner.setVisible(bool(show))
        if show:
            self.update_label.setText(f'MovieBox {self.update_notice.version} is available. Updating is optional.')

    def download_optional_update(self):
        if release_updates.notice_is_allowed(self.state['update_notifications'], self.update_notice):
            QDesktopServices.openUrl(QUrl(self.update_notice.download_url))
        self.dismiss_optional_update()

    def dismiss_optional_update(self):
        self.update_notice = None
        self.update_banner.hide()

    def skip_optional_update(self):
        if self.update_notice:
            self.state['update_notifications']['skipped_version'] = self.update_notice.version
            self.persist()
        self.dismiss_optional_update()

    def configure_optional_updates(self, enabled):
        self.state['update_notifications']['enabled'] = bool(enabled)
        self.persist()
        if not enabled:
            self.dismiss_optional_update()
        else:
            self.check_optional_updates()

    def submit(self, fn, done, *, message='Loading…', failure=None):
        if getattr(self,'closing',False):
            future=Future();future.cancel();return future
        future = self.pool.submit(fn)
        self.await_future(future, done, failure)
        if message:
            self.status.setText(message)
        return future

    def await_future(self, future, done, failure=None):
        self.jobs.setdefault(future, []).append((done, failure))

    def poll_jobs(self):
        for future, callbacks in list(self.jobs.items()):
            if not future.done():
                continue
            del self.jobs[future]
            try:
                result = future.result()
            except Exception as error:
                for done, failure in callbacks:
                    failure(str(error)) if failure else self.show_error(str(error))
            else:
                for done, failure in callbacks:
                    try:
                        done(result)
                    except Exception as error:
                        self.show_error(str(error))

    def show_error(self, message):
        self.status.setText(message[:220])
        self.status.setToolTip(message)

    def open_account(self):
        if self.api.account_token:
            answer = QMessageBox.question(self, 'MovieBox account', 'Sign out of this desktop app?',
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer == QMessageBox.Yes:
                self.api.account_token = ''
                (DATA / 'session.bin').unlink(missing_ok=True)
                self.sign_in.setText('Sign in')
                self.status.setText('Signed out on this PC.')
            return
        from account import LoginDialog
        self.login_dialog = LoginDialog(self)
        self.login_dialog.exec()

    def store_account(self, token):
        protected = protect_session(token.encode())
        (DATA / 'session.bin').write_bytes(protected)
        self.api.account_token = token
        self.sign_in.setText('Account')
        self.status.setText('Signed in to MovieBox on this PC.')

    def build_ui(self):
        from fluent_ui import build_ui
        build_ui(self, CatalogModel, PosterDelegate, VideoSurface, Artwork.fetch)

    def build_player(self):
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.7)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.positionChanged.connect(self.position_changed)
        self.player.seekableChanged.connect(lambda ready: self.apply_resume() if ready else None)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.errorOccurred.connect(self.playback_error)
        self.player.mediaStatusChanged.connect(self.media_status)
        self.player.tracksChanged.connect(self.populate_audio_tracks)
        self.player.playbackStateChanged.connect(self.play_state_changed)
        self.volume.valueChanged.connect(lambda volume: self.audio.setVolume(volume / 100))
        self.audio.mutedChanged.connect(self.update_mute_button)
        self.audio.volumeChanged.connect(self.update_mute_button)
        self.video.videoSink().videoFrameChanged.connect(self.frame_received)

    def frame_received(self, frame):
        if frame.isValid():
            if self.stack.currentIndex()==2:self.continuation_starting=False
            self.frames += 1
            self.last_frame = frame
            if getattr(self, 'prebuffering', False) and self.stack.currentIndex() == 1:
                target = getattr(self, 'prebuffer_target', 0)
                if target and self.player.duration() > 0:
                    target = min(target, max(0, self.player.duration() - 1000))
                    self.prebuffer_target = target
                if target and not self.prebuffer_seek_started:
                    self.prebuffer_seek_started = True
                    QTimer.singleShot(0, lambda: self.player.setPosition(target) if getattr(self, 'prebuffering', False) else None)
                    return
                if target and frame.startTime() >= 0 and frame.startTime() / 1000 < target - 1000:
                    return
                if not getattr(self, 'prebuffer_finish_pending', False):
                    self.prebuffer_finish_pending = True
                    QTimer.singleShot(0, self.finish_prebuffer)
            if self.frames == 1:
                if self.stack.currentIndex() == 2:
                    self.last_startup_ms = round((time.monotonic() - getattr(self, 'play_clicked_at', time.monotonic())) * 1000, 1)
                    self.status.setText('Playing' + (' · Preview limit applies' if self.preview_limit else ''))

    def play_state_changed(self, state):
        from fluent_ui import icon
        playing = state == QMediaPlayer.PlayingState
        self.pause.setText('')
        self.pause.setToolTip('Pause' if playing else 'Play')
        self.pause.setAccessibleName('Pause' if playing else 'Play')
        self.pause.setProperty('fluentGlyph','player-pause' if playing else 'player-play')
        self.pause.setIcon(icon('player-pause' if playing else 'player-play'))
        if playing and self.resume_position:
            QTimer.singleShot(200, self.apply_resume)

    def update_mute_button(self,*_):
        from fluent_ui import icon
        muted=self.audio.isMuted()
        glyph='player-volume-mute' if muted or self.audio.volume()==0 else 'player-volume-high'
        self.mute_button.setProperty('fluentGlyph',glyph);self.mute_button.setIcon(icon(glyph))
        self.mute_button.setToolTip('Volume: '+str(round(self.audio.volume()*100))+'%'+(' · Muted' if muted else ''));self.mute_button.setAccessibleName('Volume')
        self.volume_mute_toggle.setProperty('fluentGlyph',glyph);self.volume_mute_toggle.setIcon(icon(glyph))
        self.volume_mute_toggle.setToolTip('Unmute' if muted else 'Mute');self.volume_mute_toggle.setAccessibleName('Unmute' if muted else 'Mute')
        self.volume_level.setText(str(round(self.audio.volume()*100))+'%')

    def cycle_video_fit(self):
        from fluent_ui import icon
        modes=[Qt.KeepAspectRatio,Qt.KeepAspectRatioByExpanding,Qt.IgnoreAspectRatio]
        index=(modes.index(self.video.aspectRatioMode())+1)%3
        label=['Fit','Crop','Stretch'][index];glyph='player-video-scale-'+['fit','crop','stretch'][index]
        self.video.setAspectRatioMode(modes[index]);self.video_fit_button.setProperty('fluentGlyph',glyph)
        self.video_fit_button.setIcon(icon(glyph));self.video_fit_button.setToolTip('Video size: '+label);self.video_fit_button.setAccessibleName('Video size: '+label)

    def duration_changed(self, duration):
        self.progress.setMaximum(duration)
        self.apply_resume()
        expected = int((self.current_stream or {}).get('duration') or 0)
        if expected > 120 and 0 < duration < 60000 and duration < expected * 100:
            self.player.stop()
            self.show_error('MovieBox returned a short placeholder instead of the requested video. Playback stopped.')

    def populate_audio_tracks(self):
        self.audio_tracks.blockSignals(True)
        self.audio_tracks.clear()
        subject = self.playing_subject if self.stack.currentIndex() == 2 else self.current
        subject = subject or {}
        variants = audio_variants(subject)
        current_variant = next((item for item in variants if str(item['subjectId']) == str(subject.get('subjectId'))), {})
        selected = -1
        tracks = self.player.audioTracks()
        if not tracks:
            label = subject.get('_audio_language') or (language_label(current_variant) if current_variant else 'Original')
            self.audio_tracks.addItem('Audio · ' + label + ' · Loading…', None)
        for index, metadata in enumerate(tracks):
            language = metadata.value(QMediaMetaData.Language)
            language_name = getattr(language, 'name', str(language or ''))
            if not language_name or language_name in ('AnyLanguage', 'C'):
                language_name = subject.get('_audio_language') or (language_label(current_variant) if current_variant else 'Original audio')
            title = metadata.value(QMediaMetaData.Title)
            if title and str(title).lower() not in language_name.lower():
                language_name += ' · ' + str(title)
            self.audio_tracks.addItem('Audio · ' + language_name, {'kind': 'track', 'index': index})
            if index == self.player.activeAudioTrack():
                selected = self.audio_tracks.count()-1
        for variant in variants:
            if str(variant['subjectId']) != str(subject.get('subjectId')):
                suffix = ' · original' if variant.get('original') else ''
                self.audio_tracks.addItem('Audio · ' + language_label(variant) + suffix, {'kind': 'edition', 'variant': variant})
        if not self.audio_tracks.count():
            self.audio_tracks.addItem('Audio · Loading…', None)
        self.audio_tracks.setCurrentIndex(max(0, selected))
        self.audio_tracks.setVisible(True)
        self.audio_tracks.setEnabled(not self.audio_switching and bool(tracks))
        self.audio_tracks.setToolTip('Choose an audio track or dubbed edition. Playback position is preserved.')
        self.audio_tracks.blockSignals(False)

    def selected_playback_subject(self):
        if not self.current:
            return None
        preferred = self.state.get('audio_preferences', {}).get(str(self.current['subjectId']))
        if preferred and str(preferred.get('subjectId')) != str(self.current['subjectId']):
            return with_audio(self.current, preferred)
        return self.current

    def change_audio(self, index):
        if index < 0 or self.stack.currentIndex() != 2 or self.audio_switching:
            return
        option = self.audio_tracks.itemData(index) or {}
        if option.get('kind') == 'track':
            self.player.setActiveAudioTrack(option['index'])
            return
        if option.get('kind') != 'edition' or not self.playing_subject:
            return
        variant = option['variant']
        target = with_audio(self.current or self.playing_subject, variant)
        _, season, episode = self.playing_key.rsplit(':', 2)
        season, episode = int(season), int(episode)
        old_key = self.playing_key
        old_duration = float((self.current_stream or {}).get('duration') or self.player.duration()/1000)
        old_quality = self.quality.itemData(self.quality.currentIndex()) or {}
        manual_quality = int(old_quality.get('resolutions') or 0)
        self.audio_switch_intent += 1
        intent = self.audio_switch_intent
        self.audio_switching = True
        self.audio_tracks.setEnabled(False)
        self.status.setText('Preparing ' + language_label(variant) + ' audio…')
        def ready(result, restart=False):
            self.audio_switching = False
            if intent != self.audio_switch_intent or self.playing_key != old_key or self.stack.currentIndex() != 2:
                return
            streams = result['streams']
            if not result['same_cut'] and not restart:
                from PySide6.QtWidgets import QMenu
                self.populate_audio_tracks()
                self.status.setText(language_label(variant) + ' is a different cut. Keep this audio, or restart that edition from the beginning.')
                self.audio_cut_menu = QMenu(self)
                self.audio_cut_menu.addAction('Restart in ' + language_label(variant), lambda: ready(result, restart=True))
                self.audio_cut_menu.addAction('Keep current audio')
                self.audio_cut_menu.popup(self.audio_tracks.mapToGlobal(QPoint(0, self.audio_tracks.height())))
                return
            position, was_playing = (0 if restart else self.player.position()), self.player.isPlaying()
            self.save_progress()
            self.playing_subject = target
            self.playing_key = self.selection_key(target, season, episode)
            self.stream_cache[self.playing_key] = (time.monotonic(), streams)
            self.streams = streams
            self.current_stream = next((s for s in streams if int(s.get('resolutions') or 0) == manual_quality), None) or self._initial_stream(streams)
            self.quality.blockSignals(True)
            self.quality.clear()
            self.quality.addItem('Auto · ' + str(self.current_stream.get('resolutions') or '?') + 'p', None)
            for stream in streams:
                self.quality.addItem(str(stream['resolutions']) + 'p', stream)
            if manual_quality:
                for row in range(1, self.quality.count()):
                    if self.quality.itemData(row)['url'] == self.current_stream['url']:
                        self.quality.setCurrentIndex(row)
                        break
            self.quality.blockSignals(False)
            base_id = target['_audio_base_id']
            self.state.setdefault('audio_preferences', {})[base_id] = {k: variant[k] for k in ('subjectId','lanName','lanCode','original') if k in variant}
            self.state['audio_preferences'][base_id]['restart_for_cut'] = restart
            self.persist()
            self.start_video(self.current_stream['url'], position)
            self.resume_paused = not was_playing
            if not was_playing and position <= 0:
                self.player.pause()
            self.load_captions(target, self.current_stream)
            self.populate_audio_tracks()
            self.now_title.setText(target.get('title','') + (f' · S{season} E{episode}' if season else '') + ' · ' + language_label(variant))
            self.status.setText(language_label(variant) + (' audio · Different edition started from the beginning' if restart else ' audio · Keeping your position'))
        def fail(message):
            self.audio_switching = False
            self.populate_audio_tracks()
            self.show_error(message)
        def resolve():
            streams = self.api.playback(target, season, episode)
            try:
                return {'streams': matching_runtime(streams, old_duration), 'same_cut': True}
            except ValueError:
                return {'streams': full_runtime_streams(streams), 'same_cut': False}
        self.submit(resolve, ready, message='', failure=fail)

    def load_home(self):
        self.submit(self.api.home, self.home_loaded, message='Loading your catalog…')

    def home_loaded(self, result):
        self.sections = {}
        for section in result.get('operatingList') or []:
            if not section.get('subjects') or section.get('type') == 'APPOINTMENT_LIST':
                continue
            title = section.get('title', 'Discover')
            # Some server labels arrive with a UTF-8 emoji decoded twice.
            if 'ð' in title:
                try:
                    title = title.encode('latin1').decode('utf-8')
                except (ValueError, UnicodeError):
                    pass
            key = title
            key = key.replace('🔥', '').strip()
            while key in self.sections:
                key += ' ·'
            self.sections[key] = section['subjects']
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItems(list(self.sections))
        self.category.blockSignals(False)
        first_subject = next((subject for row in self.sections.values() for subject in row), None)
        if first_subject:
            if not self.hero.slides:
                self.hero.set_slides([subject for row in self.sections.values() for subject in row])
        if first_subject and not getattr(self, 'hero_feed_started', False):
            self.hero_feed_started = True
            from hero_feed import latest_titles
            self.submit(lambda: latest_titles(self.api), self.hero.set_slides, message='', failure=lambda _: None)
        active_home = self.nav_buttons['home'].isChecked() or (
            not any(button.isChecked() for button in self.nav_buttons.values())
            and self.heading.text() == 'Find your next favorite'
        )
        if active_home:
            self.show_discover()
        self.connection.setText('● Connected')
        self.catalog_ready.emit()

    def show_discover(self):
        self.stop_for_navigation()
        self.search.clear()
        from fluent_ui import set_nav
        set_nav(self, 'home')
        self.hero.setVisible(self.height() >= 700)
        self.heading.setText('Find your next favorite')
        self.page_subtitle.setText('Browse something brilliant. Make tonight a movie night.')
        self.category.show()
        self.more.hide()
        self.category_changed(self.category.currentText())

    def category_changed(self, text):
        if text in self.sections:
            self.request_generation += 1
            self.show_items(self.sections[text])

    def show_items(self, items):
        self.catalog_model.replace(items)
        has_items = bool(self.catalog_model.items)
        self.grid.setVisible(has_items)
        self.empty.setVisible(not has_items)
        if not has_items:
            name = self.heading.text().lower()
            message = ('Your next favorites start here.\nSave a title to see it in your list.' if 'list' in name else
                       'Your stories are waiting.\nStart a video and pick up here later.' if 'continue' in name else
                       'No titles found.\nTry a different name or spelling.' if 'search' in name else
                       'Nothing to show here yet.')
            self.empty.setText(message)
        self.status.setText(f'{len(self.catalog_model.items)} titles · Select a poster to explore')
        self.stack.setCurrentIndex(0)

    def browse_catalogue(self, kind):
        """Browse the full service catalogue, independently of homepage sections."""
        if kind not in ('movies', 'series'):
            return
        self.stop_for_navigation()
        from fluent_ui import set_nav
        from browse_filters import BrowseCatalogue
        if self.catalogue_backend is None:
            self.catalogue_backend = BrowseCatalogue(self.api)
        self.catalogue_kind, self.catalogue_page = kind, 1
        self.hero.hide()
        self.search.clear()
        self.category.hide()
        self.more.hide()
        self.heading.setText('Movies' if kind == 'movies' else 'TV Shows')
        self.page_subtitle.setText('Browse the full catalogue · Choose filters, then Apply')
        set_nav(self, kind)
        self.populate_catalogue_filters(kind)
        self.catalogue_filter_panel.show()
        self.request_catalogue_page()

    def populate_catalogue_filters(self, kind):
        options = self.catalogue_backend.options(kind)
        selected = self.catalogue_selections.get(kind, {})
        if not isinstance(selected, dict):
            selected = {}
        for field, picker in self.catalogue_filter_fields.items():
            picker.blockSignals(True)
            picker.clear()
            for option in options[field]:
                picker.addItem(option['label'], option['value'])
            row = picker.findData(selected.get(field))
            picker.setCurrentIndex(max(0, row))
            picker.blockSignals(False)

    def apply_catalogue_filters(self):
        if not self.catalogue_kind:
            return
        self.capture_catalogue_view()
        self.catalogue_selections[self.catalogue_kind] = {
            name: picker.currentData() for name, picker in self.catalogue_filter_fields.items()
        }
        self.state['catalogue_filters'] = self.catalogue_selections
        self.persist()
        self.catalogue_page = 1
        self.request_generation += 1
        self.request_catalogue_page(force=True)

    def reset_catalogue_filters(self):
        if not self.catalogue_kind:
            return
        self.catalogue_selections.pop(self.catalogue_kind, None)
        self.populate_catalogue_filters(self.catalogue_kind)
        self.apply_catalogue_filters()

    def request_catalogue_page(self, append=False, force=False):
        kind, page, generation = self.catalogue_kind, self.catalogue_page, self.request_generation
        selection = dict(self.catalogue_selections.get(kind, {}))
        cache_key = self.catalogue_cache.key(kind, selection)
        self.active_catalogue_cache_key = cache_key
        cached = self.catalogue_cache.get(cache_key)
        previous_items = list(self.catalog_model.items) if append else []
        if cached and not append:
            self.catalogue_pending_refresh_key = ''
            self.show_items(cached['items'])
            self.more.setEnabled(True); self.more.setVisible(bool(cached.get('has_more')))
            self.more.setText('Load more')
            self.catalogue_next_page = int(cached.get('next_page',2))
            self.catalogue_page = int(cached.get('page',1))
            self.catalogue_apply.setText('Apply filters')
            row = max(0,min(int(cached.get('row',0)),len(cached['items'])-1))
            if cached['items']:self.grid.setCurrentIndex(self.catalog_model.index(row,0))
            def restore_scroll():
                if self.catalogue_kind==kind and self.active_catalogue_cache_key==cache_key:
                    self.grid.verticalScrollBar().setValue(int(cached.get('scroll',0)))
            QTimer.singleShot(0,restore_scroll)
            if not force and time.time()-float(cached.get('at',0))<self.catalogue_cache.TTL:
                return
        if not cached or append:
            self.more.setEnabled(False)
            self.catalogue_apply.setText('Loading…')
        if not append and not cached:
            self.show_items([])
            self.empty.setText('Loading the MovieBox catalogue…')
            self.more.hide()
        def done(result):
            old = cached
            first_count = int((old or {}).get('first_count',len(result['items'])))
            unchanged = old and not append and old['items'][:first_count] == [compact_catalogue_subject(item) for item in result['items']]
            if unchanged:
                old['at']=time.time();self.catalogue_cache.put(cache_key,old)
            else:
                merged = previous_items + result['items'] if append else result['items']
                seen_ids=set();merged=[item for item in merged if not (str(item['subjectId']) in seen_ids or seen_ids.add(str(item['subjectId'])))]
                self.catalogue_cache.put(cache_key,{'items':merged,'at':time.time(),'has_more':result['has_more'],'next_page':result['next_page'],'page':page,'first_count':first_count if append else len(result['items']),'scroll':0,'row':0})
            self.submit(self.catalogue_cache.flush,lambda _:None,message='',failure=lambda _:None)
            if generation != self.request_generation or kind != self.catalogue_kind:
                return
            if unchanged:
                self.catalogue_apply.setText('Apply filters');self.more.setEnabled(True)
                return
            if cached and not append and not force and (self.grid.hasFocus() or self.grid.verticalScrollBar().value()>0):
                self.catalogue_pending_refresh_key=cache_key
                self.catalogue_apply.setText('New titles · Apply')
                self.status.setText('New titles are available. Apply filters to refresh this view.')
                return
            previous = previous_items if append else []
            seen = {str(item.get('subjectId')) for item in previous}
            items = previous + [item for item in result['items'] if str(item.get('subjectId')) not in seen]
            self.show_items(items)
            self.more.setEnabled(True)
            self.more.setVisible(result['has_more'])
            self.more.setText('Load more')
            self.catalogue_next_page = result['next_page']
            self.catalogue_apply.setEnabled(True)
            self.catalogue_apply.setText('Apply filters')
            self.catalogue_reset.setEnabled(True)
            labels = {'rate': 'Rating', 'classify': 'Audio'}
            filters = [f'{labels.get(field, field.title())}: {value}{"+" if field == "rate" else ""}' for field, value in selection.items()
                       if value not in ('All', 'ForYou', '', None)]
            self.page_subtitle.setText(' · '.join(filters) if filters else 'Browse the full MovieBox catalogue')
            if not items:
                self.empty.setText('No titles match these filters.\nTry another selection or Reset.')
        def failed(message):
            if generation != self.request_generation or kind != self.catalogue_kind:
                return
            self.more.setEnabled(True)
            self.catalogue_apply.setEnabled(True)
            self.catalogue_apply.setText('Apply filters')
            self.catalogue_reset.setEnabled(True)
            if cached:
                self.status.setText('Could not check for new titles. Your current catalogue is still available.')
            else:self.show_error(message)
            if not append and not cached:
                self.empty.setText('The catalogue could not load.\nUse Apply filters to retry.')
        self.submit(lambda: self.catalogue_backend.page(kind, selection, page), done,
                    message='' if cached else 'Loading catalogue…', failure=failed)

    def run_search(self):
        keyword = self.search.text().strip()
        skip = getattr(self, 'suggestion_skip', ('', 0))
        if skip[0] == keyword and time.monotonic() < skip[1]:
            return
        if hasattr(self, 'completer'):
            self.completer.popup().hide()
        if not keyword:
            self.show_discover()
            return
        self.stop_for_navigation()
        self.hero.hide()
        from fluent_ui import set_nav
        set_nav(self, '')
        self.page_subtitle.setText('Results for “' + keyword + '”')
        self.search_keyword, self.search_page = keyword, 1
        self.request_generation += 1
        generation = self.request_generation
        self.heading.setText('Search results')
        self.category.hide()
        self.more.hide()
        self.submit(lambda: self.api.search(keyword), lambda result: self.search_loaded(result, generation),
                    message=f'Searching for “{keyword}”…')

    def search_loaded(self, result, generation, append=False):
        if generation != self.request_generation:
            return
        items = result.get('items') or []
        self.show_items(self.catalog_model.items + items if append else items)
        self.more.setVisible(bool((result.get('pager') or {}).get('hasMore')))
        self.more.setEnabled(True)

    def load_more(self):
        if self.catalogue_kind:
            self.catalogue_page = self.catalogue_next_page
            self.request_catalogue_page(append=True)
            return
        self.search_page += 1
        page, keyword, generation = self.search_page, self.search_keyword, self.request_generation
        self.more.setEnabled(False)
        self.submit(lambda: self.api.search(keyword, page), lambda result: self.search_loaded(result, generation, True),
                    failure=lambda message: (self.more.setEnabled(True), self.show_error(message)))

    def setup_suggestions(self):
        self.suggestion_model = QStandardItemModel(self)
        self.completer = QCompleter(self.suggestion_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.completer.setMaxVisibleItems(8)
        self.search.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.accept_suggestion)
        self.suggestion_timer = QTimer(self)
        self.suggestion_timer.setSingleShot(True)
        self.suggestion_timer.timeout.connect(self.request_suggestions)
        self.search.textEdited.connect(lambda text: self.suggestion_timer.start(220))
        self.search.textChanged.connect(lambda text: self.completer.popup().hide() if len(text.strip()) < 2 else None)
        self.suggestion_inflight = None
        self.suggestion_cache = {}
        self.suggestion_skip = ('', 0)

    def request_suggestions(self):
        query = self.search.text().strip()
        if len(query) < 2 or not self.search.hasFocus():
            self.completer.popup().hide()
            return
        if self.suggestion_inflight and not self.suggestion_inflight.done():
            self.suggestion_timer.start(120)
            return
        def ready(items):
            if query != self.search.text().strip() or not self.search.hasFocus():
                return
            self.suggestion_cache[query] = (time.monotonic(), items)
            self.suggestion_model.clear()
            for suggestion in items:
                title = suggestion.get('word') or (suggestion.get('subject') or {}).get('title') or suggestion.get('title')
                if title:
                    item = QStandardItem(title)
                    item.setData(suggestion, Qt.UserRole)
                    self.suggestion_model.appendRow(item)
            if self.suggestion_model.rowCount():
                self.completer.setCompletionPrefix(query)
                popup = self.completer.popup()
                popup.setMinimumWidth(max(350, self.search.width()))
                popup.setStyleSheet('QListView{padding:5px;border:1px solid #384758;border-radius:8px}QListView::item{padding:10px 12px;min-height:22px}')
                self.completer.complete()
        cached = self.suggestion_cache.get(query)
        if cached and time.monotonic() - cached[0] < 300:
            ready(cached[1])
        else:
            self.suggestion_inflight = self.submit(lambda: self.api.suggest(query), ready, message='', failure=lambda message: None)

    def accept_suggestion(self, index):
        item = index.data(Qt.UserRole) or {}
        text = item.get('word') or index.data(Qt.DisplayRole) or self.search.text()
        self.search.setText(text)
        self.completer.popup().hide()
        subject = item.get('subject')
        if subject and subject.get('subjectId'):
            self.open_detail(subject)
        else:
            self.run_search()
        self.suggestion_skip = (self.search.text().strip(), time.monotonic() + .15)

    def selection_key(self, subject=None, season=None, episode=None):
        subject = subject or self.selected_playback_subject()
        if not subject:
            return ''
        movie = int(subject.get('subjectType') or 0) == 1
        season = 0 if movie else int(season if season is not None else (self.season.currentData() or {}).get('se') or 0)
        episode = 0 if movie else int(episode if episode is not None else self.episode.currentData() or 0)
        return f'{subject["subjectId"]}:{season}:{episode}'

    def preferred_subtitle_language(self, key):
        return (self.state.get('subtitle_tracks') or {}).get(key) or self.state.get('subtitle_language') or 'en'

    def _caption_future(self, key, subject, stream, language=None):
        language = language or self.preferred_subtitle_language(key)
        identity = (key, language)
        existing = self.caption_requests.get(identity)
        if existing:
            if not existing.done():
                return existing
            if not existing.exception() and existing.result().get('cues'):
                return existing
        _, season, episode = key.rsplit(':', 2)
        future = self.pool.submit(lambda: self.subtitle_store.prepare(key, language,
            lambda: self.api.captions(subject, stream['id'], season=int(season), episode=int(episode))))
        self.caption_requests[identity] = future
        return future

    def _initial_stream(self, streams):
        eligible = [s for s in streams if int(s.get('resolutions') or 0) <= 1080] or streams
        bandwidth = float(self.state.get('bandwidth_mbps') or 8)
        return select_quality(eligible, bandwidth) or eligible[-1]

    def _stream_future(self, subject, season, episode):
        key = self.selection_key(subject, season, episode)
        cached = self.stream_cache.get(key)
        if cached and time.monotonic() - cached[0] < 300:
            future = Future()
            future.set_result(cached[1])
            return future
        existing = self.stream_requests.get(key)
        if existing and not existing.done():
            return existing
        subject = subject.copy()
        def stored(streams):
            self.stream_cache[key] = (time.monotonic(), streams)
            while len(self.stream_cache) > 64:
                stale = next(iter(self.stream_cache))
                del self.stream_cache[stale]
                self.stream_requests.pop(stale, None)
            self.maybe_prepare_media(key, subject, streams)
            if self.state.get('subtitle_enabled', True):
                self._caption_future(key, subject, self._initial_stream(streams))
        base_id = subject.get('_audio_base_id')
        base_key = str(base_id or subject['subjectId']) + f':{season}:{episode}'
        previous_duration = float((self.state['history'].get(base_key) or {}).get('duration') or 0) / 1000
        def resolve():
            streams = self.api.playback(subject, season, episode)
            if not streams:raise ValueError('No playable source is available for this episode.')
            if subject.get('_audio_restart_for_cut'):
                streams = full_runtime_streams(streams)
            elif base_id and str(base_id) != str(subject['subjectId']):
                duration = previous_duration
                if duration <= 0:
                    base_streams = self.api.playback({**subject, 'subjectId': str(base_id)}, season, episode)
                    duration = max(float(stream.get('duration') or 0) for stream in base_streams)
                streams = matching_runtime(streams, duration)
            return streams
        future = self.submit(resolve, stored, message='', failure=lambda message: None)
        self.stream_requests[key] = future
        return future

    def maybe_prepare_media(self, key, subject, streams):
        if self.stack.currentIndex() != 1 or key != self.selection_key() or self.player.isPlaying():
            return
        if QApplication.activePopupWidget() or self.season.view().isVisible() or self.episode.view().isVisible():
            QTimer.singleShot(150, lambda: self.maybe_prepare_media(key, subject, streams))
            return
        stream = self._initial_stream(streams)
        if self.prepared_media and self.prepared_media.get('key') == key and self.prepared_media.get('remote') == stream['url']:
            return
        self.save_progress()
        self.end_prebuffer()
        self.player.stop()
        local = self.bridge.register(stream['url'], stream.get('headers'))
        self.prepared_media = {'key': key, 'remote': stream['url'], 'local': local}
        self.current_stream = stream
        self.player.setSource(QUrl(local))
        self.prebuffer_muted = self.audio.isMuted()
        history_key = str(subject.get('_audio_base_id') or subject['subjectId']) + ':' + ':'.join(key.rsplit(':', 2)[1:])
        self.prebuffer_target = int((self.state['history'].get(key) or self.state['history'].get(history_key) or {}).get('position') or 0)
        self.prebuffer_seek_started = False
        self.prebuffer_finish_pending = False
        self.prebuffering = True
        self.audio.setMuted(True)
        self.player.play()

    def finish_prebuffer(self):
        if getattr(self, 'prebuffering', False) and self.stack.currentIndex() == 1:
            self.player.pause()
            if self.prepared_media:
                self.prepared_media['position'] = self.player.position()
            self.end_prebuffer()

    def end_prebuffer(self):
        if getattr(self, 'prebuffering', False):
            self.prebuffering = False
            self.audio.setMuted(self.prebuffer_muted)

    def schedule_prefetch(self):
        if not self.current or not self.detail_data:
            return
        generation, key = self.request_generation, self.selection_key()
        def prepare():
            if generation != self.request_generation or key != self.selection_key() or self.stack.currentIndex() != 1:
                return
            if QApplication.activePopupWidget() or self.season.view().isVisible() or self.episode.view().isVisible():
                QTimer.singleShot(150, prepare)
                return
            movie = int(self.current.get('subjectType') or 0) == 1
            season = 0 if movie else int((self.season.currentData() or {}).get('se') or 0)
            episode = 0 if movie else int(self.episode.currentData() or 0)
            if movie or (season > 0 and episode > 0):
                selected_subject = self.selected_playback_subject()
                future = self._stream_future(selected_subject, season, episode)
                if future.done() and not future.exception():
                    self.maybe_prepare_media(key, selected_subject, future.result())
        QTimer.singleShot(350, prepare)

    def open_detail(self, subject):
        if not subject:
            return
        if getattr(self, 'prebuffering', False):
            self.player.stop()
            self.end_prebuffer()
        if getattr(self, 'hero_auto_play', '') != str(subject['subjectId']):
            self.hero_auto_play = ''
        self.current, self.detail_data = subject, None
        self.request_generation += 1
        generation = self.request_generation
        self.stack.setCurrentIndex(1)
        self.detail_title.setText(subject.get('title', ''))
        self.description.setText('Loading description…')
        self.detail_cover.clear()
        self.watch.setEnabled(False)
        self.trailer.setEnabled(False)
        self.save.setEnabled(False)
        self.detail_notice.setText('')
        self.completer.popup().hide()
        def hint():
            if generation != self.request_generation or self.stack.currentIndex() != 1:
                return
            kind = int(subject.get('subjectType') or 0)
            if kind == 1:
                self._stream_future(subject, 0, 0)
            elif kind == 2:
                previous = [(k, v) for k, v in self.state['history'].items() if k.startswith(str(subject['subjectId']) + ':')]
                season, episode = 1, 1
                if previous:
                    k, _ = max(previous, key=lambda pair: pair[1].get('updated', 0))
                    _, se, ep = k.split(':')
                    season, episode = int(se), int(ep)
                self._stream_future(subject, season, episode)
        QTimer.singleShot(150, hint)
        self.submit(lambda: self.api.detail(subject), lambda result: self.detail_loaded(result, generation))
        self.load_detail_art(subject, generation)

    def load_detail_art(self, subject, generation):
        url = (subject.get('cover') or {}).get('url')
        self.detail_art_url = url
        if not url:
            return
        def ready(decoded):
            if generation != self.request_generation:
                return
            if not decoded.isNull():
                image = QPixmap.fromImage(decoded)
                self.detail_cover.setPixmap(image)
        self.submit(lambda: Artwork.fetch_image(url), ready, message='', failure=lambda message: None)

    def detail_loaded(self, data, generation):
        if generation != self.request_generation:
            return
        self.detail_data = data
        self.current = data.get('subject') or self.current
        item = self.current
        if (item.get('cover') or {}).get('url') != getattr(self,'detail_art_url',None):
            self.load_detail_art(item,generation)
        self.detail_title.setText(item.get('title', ''))
        self.detail_meta.setText('  ·  '.join(str(v) for v in [str(item.get('releaseDate') or '')[:4],
            item.get('genre'), item.get('countryName'), ('IMDb ' + str(item['imdbRatingValue'])) if item.get('imdbRatingValue') else ''] if v))
        self.description.setText(item.get('description') or 'No description is available.')
        self.season.blockSignals(True)
        self.season.clear()
        is_series = bool(data.get('isSeries', int(item.get('subjectType') or 0) == 2))
        seasons = ((data.get('resource') or {}).get('seasons') or []) if is_series else []
        for season in seasons:
            self.season.addItem('Season ' + str(season.get('se', 0)), season)
        self.season.blockSignals(False)
        self.season.setVisible(bool(seasons))
        self.season_row.setVisible(bool(seasons))
        self.episode.hide()
        self.episode_panel.setVisible(bool(seasons))
        self.populate_episodes()
        previous = [(key, value) for key, value in self.state['history'].items()
                    if key.startswith(str(item['subjectId']) + ':')]
        if previous:
            key, _ = max(previous, key=lambda pair: pair[1].get('updated', 0))
            try:
                _, saved_season, saved_episode = key.split(':')
                for index in range(self.season.count()):
                    if str((self.season.itemData(index) or {}).get('se')) == saved_season:
                        self.season.setCurrentIndex(index)
                        break
                for index in range(self.episode.count()):
                    if str(self.episode.itemData(index)) == saved_episode:
                        self.episode.setCurrentIndex(index)
                        break
            except (ValueError, AttributeError):
                pass
        self.watch.setEnabled(not data.get('isForbid') and bool(item.get('hasResource', True)))
        self.trailer.setEnabled(bool(((item.get('trailer') or {}).get('videoAddress') or {}).get('url')))
        self.save.setEnabled(True)
        self.save.setText('Saved' if str(item['subjectId']) in self.state['saved'] else 'My list')
        self.detail_notice.setText('Pick your quality and subtitle language when playback begins.')
        self.status.setText('Ready · Choose an episode or press Watch')
        self.detail_ready.emit()
        self.schedule_prefetch()
        if getattr(self, 'hero_auto_play', '') == str(item['subjectId']):
            self.hero_auto_play = ''
            QTimer.singleShot(0, self.watch_current)

    def populate_episodes(self, *_):
        season = self.season.currentData() or {}
        self.episode.blockSignals(True)
        self.episode.clear()
        self.episode_cards.clear()
        explicit = str(season.get('allEp') or '')
        numbers = season.get('episodeNumbers') or ([int(n) for n in explicit.split(',') if n.strip().isdigit()] if explicit else range(1, min(int(season.get('maxEp') or 0), 10000) + 1))
        self.episode_row_by_number = {}
        for number in numbers:
            self.episode.addItem(f'Episode {number}', number)
            item = QListWidgetItem(f'Episode {number}')
            item.setData(Qt.UserRole, int(number))
            item.setSizeHint(QSize(116, 46))
            self.episode_row_by_number[int(number)] = self.episode_cards.count()
            self.episode_cards.addItem(item)
        self.episode.blockSignals(False)
        self.episode_heading.setText(f'Season {season.get("se", 1)} · {self.episode.count()} episodes')
        rows = max(1, (self.episode.count() + 6) // 7)
        self.episode_cards.setFixedHeight(min(320, rows * 56 + 10))
        self.update_episode_selection()

    def update_episode_selection(self, *_):
        number = self.episode.currentData()
        row = getattr(self, 'episode_row_by_number', {}).get(number)
        if row is not None:
            self.episode_cards.setCurrentRow(row)
        self.schedule_prefetch()

    def activate_episode(self, item):
        index = self.episode.findData(item.data(Qt.UserRole))
        if index >= 0:
            self.episode.setCurrentIndex(index)
            self.watch_current()

    def watch_current(self, continuation=False):
        continuation = continuation is True
        self.continuation_starting=continuation
        if not self.current or not self.detail_data:
            return
        subject = self.selected_playback_subject().copy()
        movie = int(subject.get('subjectType') or 0) == 1
        season = 0 if movie else int((self.season.currentData() or {}).get('se') or 0)
        episode = 0 if movie else int(self.episode.currentData() or 0)
        self.play_clicked_at = time.monotonic()
        self.play_intent += 1
        intent = self.play_intent
        self.preview_limit = 0
        policy = {} if self.api.native else self.detail_data.get('accessStrategy') or subject.get('accessStrategy') or {}
        if policy.get('requiredVipLevel', 0) > 0 and (not episode or episode > policy.get('freeEpisodeCount', 0)):
            preview = int(policy.get('previewSeconds') or 0)
            if preview <= 0:
                if continuation:
                    self.finish_playback('The next episode is not available for playback.');return
                self.show_error('This selection requires a MovieBox membership. No account is signed in to this preview.')
                return
            self.preview_limit = preview * 1000
        generation = self.request_generation
        self.watch.setEnabled(False)
        def ready(streams):
            if generation != self.request_generation or intent != self.play_intent:
                return
            if not streams:
                fail('No playable source is available for the next episode.');return
            self.save_progress()
            self.watch.setEnabled(True)
            self.playing_subject = subject
            self.playback_return_view = 1
            self.playing_key = f'{subject["subjectId"]}:{season}:{episode}'
            self.continuation_starting=continuation
            self.now_title.setText(subject['title'] + (f' · S{season} E{episode}' if season else ''))
            self.streams = streams
            self.current_stream = self._initial_stream(streams)
            self.quality.blockSignals(True)
            self.quality.clear()
            self.quality.addItem('Auto · ' + str(self.current_stream.get('resolutions') or '?') + 'p', None)
            for stream in streams:
                self.quality.addItem(str(stream.get('resolutions') or 'Auto') + 'p', stream)
            for stream in self.api.last_play_info.get('streams') or []:
                if stream.get('vipLocked') and stream.get('resolutions'):
                    self.quality.addItem(str(stream['resolutions']) + 'p · account required', None)
                    self.quality.model().item(self.quality.count() - 1).setEnabled(False)
            self.quality.blockSignals(False)
            base_key = str(subject.get('_audio_base_id') or subject['subjectId']) + f':{season}:{episode}'
            old = self.state['history'].get(self.playing_key) or self.state['history'].get(base_key) or {}
            position = 0 if old.get('completed') else int(old.get('position') or 0)
            if subject.get('_audio_restart_for_cut') and str(old.get('audio_subject_id') or '') != str(subject['subjectId']):
                position = 0
            self.start_video(self.current_stream['url'], position)
            self.load_captions(subject, self.current_stream)
            self.populate_audio_tracks()
            self.last_auto_probe = 0
            self.auto_bandwidth = 0
            QTimer.singleShot(2500, self.adapt_quality)
            self.playback_ready.emit()
        def fail(message):
            if generation != self.request_generation or intent != self.play_intent:return
            self.watch.setEnabled(True)
            if continuation:self.finish_playback('The next episode could not be played. '+message)
            else:self.show_error(message)
        self.status.setText('Preparing playback…')
        self.await_future(self._stream_future(subject, season, episode), ready, fail)

    def watch_trailer(self):
        self.playback_return_view = 1
        video = ((self.current.get('trailer') or {}).get('videoAddress') or {})
        if video.get('url'):
            self.playing_subject, self.playing_key = None, ''
            self.preview_limit = 0
            self.quality.clear()
            self.clear_captions()
            self.now_title.setText('Trailer · ' + self.current.get('title', ''))
            self.start_video(video['url'])

    def start_video(self, url, position=0):
        self.volume_menu.hide()
        self.end_handled = False
        self.player_episode_panel.hide()
        self.episode_browser_button.setVisible(bool(self.playing_subject and int(self.playing_subject.get('subjectType') or 0)==2))
        self.next_up_panel.hide()
        self.end_prebuffer()
        self.last_progress_checkpoint = None
        self.resume_paused = False
        prepared = self.prepared_media
        reuse = bool(prepared and prepared['key'] == self.playing_key and prepared['remote'] == url
                     and self.player.source().toString() == prepared['local'])
        if not reuse:
            self.player.stop()
        at_saved_position = reuse and abs(prepared.get('position', -100000) - position) < 1500
        self.resume_position = 0 if at_saved_position else position
        self.resume_not_before = time.monotonic() + .15
        self.frames = 0
        self.stack.setCurrentIndex(2)
        self.download_button.setEnabled(bool(self.current_stream) and not self.preview_limit and bool(self.playing_subject))
        if not reuse and url.startswith(('https://', 'http://')):
            headers = (self.current_stream or {}).get('headers') or {'User-Agent': 'Mozilla/5.0'}
            if self.current_stream and self.current_stream.get('signHeaderKey') and self.current_stream.get('signCookie'):
                headers = {**headers, self.current_stream['signHeaderKey']: self.current_stream['signCookie']}
            url = self.bridge.register(url, headers)
        if not reuse:
            self.player.setSource(QUrl(url))
        self.prepared_media = None
        self.apply_resume()
        self.player.play()
        self.status.setText('Opening video…')

    def media_status(self, status):
        if self.stack.currentIndex() != 2:
            return
        if status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
            self.apply_resume()
            if not self.frames:
                self.status.setText('Video loaded · Waiting for the first frame…')
        elif status == QMediaPlayer.BufferingMedia:
            self.status.setText('Buffering…')
        elif status == QMediaPlayer.EndOfMedia:
            if self.end_handled:return
            self.end_handled=True
            self.save_progress();self.next_up_panel.hide()
            if self.next_episode_target():
                intent=self.play_intent
                QTimer.singleShot(0,lambda:self.play_next_episode() if self.stack.currentIndex()==2 and self.play_intent==intent else None)
            else:self.finish_playback('Finished · Your place is saved.')

    def apply_resume(self):
        if (self.resume_position and self.stack.currentIndex() == 2 and self.player.isSeekable()
                and self.player.playbackState() == QMediaPlayer.PlayingState
                and time.monotonic() >= getattr(self, 'resume_not_before', 0)):
            target = self.resume_position
            duration = self.player.duration()
            if duration > 0:
                target = min(target, max(0, duration - 1000))
            self.player.setPosition(target)
            self.resume_position = 0
            if getattr(self, 'resume_paused', False):
                self.resume_paused = False
                self.player.pause()

    def seek_to(self, position):
        self.seek_grace_until = time.monotonic() + 3
        self.resume_position = 0
        position = max(0, min(int(position), self.player.duration()))
        if self.preview_limit:
            position = min(position, self.preview_limit)
        self.player.setPosition(position)
        self.save_progress()

    def play_next_episode(self):
        for picker in (self.quality,self.audio_tracks,self.caption_selector):picker.hidePopup()
        target=self.next_episode_target()
        if not target:
            self.finish_playback('Finished · No more episodes are available.');return
        self.save_progress();self.next_up_panel.hide()
        season,episode=target
        for row in range(self.season.count()):
            if int((self.season.itemData(row) or {}).get('se') or 0)==season:
                self.season.setCurrentIndex(row);break
        row=self.episode.findData(episode)
        if row<0:self.finish_playback('No playable next episode is available.');return
        self.episode.setCurrentIndex(row)
        self.watch_current(continuation=True)

    def next_episode_target(self):
        if not self.playing_subject or int(self.playing_subject.get('subjectType') or 0)!=2 or not self.playing_key:return None
        try:
            _,season,episode=self.playing_key.rsplit(':',2)
            return following_episode(((self.detail_data or {}).get('resource') or {}).get('seasons') or [],int(season),int(episode))
        except (ValueError,TypeError):return None

    def finish_playback(self,message='Finished'):
        self.volume_menu.hide()
        self.continuation_starting=False
        self.player_episode_panel.hide()
        for picker in (self.quality,self.audio_tracks,self.caption_selector):picker.hidePopup()
        self.save_progress();self.next_up_panel.hide()
        if self.cinema and self.cinema.isVisible():self.cinema.leave()
        self.player.stop();self.prepared_media=None
        self.stack.setCurrentIndex(self.playback_return_view if self.playback_return_view in (0,1,3) else (1 if self.current else 0))
        self.detail_notice.setText(message);self.status.setText(message)
        self.watch.setEnabled(bool(self.current))

    def playback_error(self,error,text):
        if self.continuation_starting:
            self.finish_playback('The next episode could not start. '+text)
        else:self.show_error('Playback error: '+text)

    def dismiss_next_up(self):
        self.next_up_dismissed_key=self.playing_key;self.next_up_panel.hide()

    def open_player_episodes(self):
        if not self.playing_subject or int(self.playing_subject.get('subjectType') or 0)!=2:return
        records=((self.detail_data or {}).get('resource') or {}).get('seasons') or []
        if not records:return
        _,season,episode=self.playing_key.rsplit(':',2)
        self.player_season_picker.blockSignals(True);self.player_season_picker.clear()
        for record in sorted(records,key=lambda item:int(item.get('se') or 0)):
            if int(record.get('se') or 0)>0:self.player_season_picker.addItem('Season '+str(record['se']),record)
        for row in range(self.player_season_picker.count()):
            if int(self.player_season_picker.itemData(row).get('se') or 0)==int(season):self.player_season_picker.setCurrentIndex(row);break
        self.player_season_picker.setFixedWidth(max(128,min(180,max((self.player_season_picker.fontMetrics().horizontalAdvance(self.player_season_picker.itemText(i)) for i in range(self.player_season_picker.count())),default=0)+56)))
        self.player_season_picker.blockSignals(False);self.populate_player_episodes()
        self.next_up_panel.hide();self.player_episode_panel.show();self.position_player_episodes();self.player_episode_panel.raise_()
        self.player_episode_panel.activateWindow();self.player_season_picker.setFocus()
        self.player_episode_animation=QVariantAnimation(self)
        self.player_episode_animation.setStartValue(.25);self.player_episode_animation.setEndValue(1.0);self.player_episode_animation.setDuration(150)
        origin=self.player_episode_panel.pos()
        def reveal(value):
            self.player_episode_panel.setWindowOpacity(value)
            self.player_episode_panel.move(origin.x()+round((1-value)*32),origin.y())
        self.player_episode_animation.valueChanged.connect(reveal)
        self.player_episode_animation.start()

    def populate_player_episodes(self,*_):
        record=self.player_season_picker.currentData() or {};self.player_episode_list.clear()
        current=self.playing_key.rsplit(':',2)[-2:] if self.playing_key else []
        for number in episode_numbers(record):
            active=current==[str(record.get('se')),str(number)]
            item=QListWidgetItem(f'Episode {number}'+('  ·  Playing' if active else ''))
            item.setData(Qt.UserRole,(int(record.get('se') or 0),number));item.setSizeHint(QSize(300,48))
            self.player_episode_list.addItem(item)
            if active:self.player_episode_list.setCurrentItem(item)
        if self.player_episode_list.currentRow()<0 and self.player_episode_list.count():self.player_episode_list.setCurrentRow(0)
        self.player_episode_list.scrollToItem(self.player_episode_list.currentItem()) if self.player_episode_list.currentItem() else None

    def close_player_episodes(self):
        if hasattr(self,'player_episode_animation'):self.player_episode_animation.stop()
        self.player_episode_panel.hide()
        if self.cinema and self.cinema.isVisible():self.cinema.activateWindow();self.cinema.reveal_controls()
        else:self.activateWindow()
        self.episode_browser_button.setFocus()

    def position_player_episodes(self):
        panel=getattr(self,'player_episode_panel',None)
        if panel is None or not panel.isVisible():return
        origin=self.video.mapToGlobal(QPoint(0,0));width=min(440,max(300,self.video.width()-24));height=max(180,self.video.height()-24)
        panel.resize(width,height);panel.move(origin.x()+self.video.width()-width-12,origin.y()+12)

    def play_player_episode(self,item):
        if not self.player_episode_panel.isVisible():return
        season,episode=item.data(Qt.UserRole)
        if self.playing_key.endswith(f':{season}:{episode}'):
            self.close_player_episodes();return
        self.close_player_episodes()
        for row in range(self.season.count()):
            if int((self.season.itemData(row) or {}).get('se') or 0)==season:self.season.setCurrentIndex(row);break
        row=self.episode.findData(episode)
        if row>=0:self.episode.setCurrentIndex(row);self.watch_current(continuation=True)

    def position_next_up(self):
        if not hasattr(self,'next_up_panel') or not self.next_up_panel.isVisible():return
        origin=self.video.mapToGlobal(QPoint(0,0))
        self.next_up_panel.adjustSize()
        self.next_up_panel.move(origin.x()+max(10,self.video.width()-self.next_up_panel.width()-24),origin.y()+max(12,self.video.height()-self.next_up_panel.height()-125))

    def update_next_up(self,position):
        target=self.next_episode_target()
        threshold=next_up_at(self.player.duration(),self.current_stream)
        show=self.stack.currentIndex()==2 and not self.player_episode_panel.isVisible() and target and threshold is not None and position>=threshold and self.next_up_dismissed_key!=self.playing_key
        if not show:self.next_up_panel.hide();return
        marker=(self.playing_key,target)
        if getattr(self,'next_prefetch_marker',None)!=marker:
            self.next_prefetch_marker=marker
            self._stream_future(self.selected_playback_subject().copy(),target[0],target[1])
        self.next_up_label.setText(f'Up next · Season {target[0]}, Episode {target[1]}')
        if not self.next_up_panel.isVisible():
            self.next_up_panel.show();self.next_up_panel.raise_()
        self.position_next_up()

    def video_click(self):
        if self.suppress_video_release:
            self.suppress_video_release=False;return
        self.video_click_state=self.player.playbackState()
        self.video_click_source=self.player.source()
        self.video_click_time=time.monotonic()
        self.toggle_pause()

    def video_double_click(self):
        if time.monotonic()-self.video_click_time<(QApplication.doubleClickInterval()+100)/1000 and getattr(self,'video_click_source',None)==self.player.source():
            self.player.play() if self.video_click_state==QMediaPlayer.PlayingState else self.player.pause()
        self.video_click_time=0;self.suppress_video_release=True
        QTimer.singleShot(QApplication.doubleClickInterval()+50,lambda:setattr(self,'suppress_video_release',False))
        self.toggle_fullscreen()

    def change_quality(self, index):
        if index < 0 or self.stack.currentIndex() != 2:
            return
        if index == 0:
            self.last_auto_probe = 0
            self.adapt_quality()
            return
        stream = self.quality.itemData(index)
        if stream:
            try:
                matching_runtime([stream], float((self.current_stream or {}).get('duration') or self.player.duration() / 1000))
            except ValueError:
                self.quality.blockSignals(True)
                old = next((row for row in range(1, self.quality.count()) if (self.quality.itemData(row) or {}).get('url') == (self.current_stream or {}).get('url')), 0)
                self.quality.setCurrentIndex(old)
                self.quality.blockSignals(False)
                self.show_error('That quality is a different cut. Keeping the current video and your place.')
                return
            was_playing = self.player.isPlaying()
            self.current_stream = stream
            self.start_video(stream['url'], self.player.position())
            if not was_playing:
                self.player.pause()

    def position_changed(self, position):
        self.update_next_up(position)
        if (position > 0 and self.stack.currentIndex() == 2 and self.playing_subject
                and self.playing_key and not self.resume_position and not getattr(self, 'prebuffering', False)):
            self.last_progress_checkpoint = (self.playing_key, position, self.player.duration())
        if not self.progress.isSliderDown():
            self.progress.setValue(position)
        self.clock.setText(timestamp(position) + ' / ' + timestamp(self.player.duration()))
        self.video.set_caption(self.subtitle_track.at(position - self.subtitle_delay.value()))
        if self.preview_limit and position >= self.preview_limit:
            self.player.pause()
            self.status.setText('MovieBox preview ended. A membership is required to continue this selection.')

    def clear_captions(self):
        self.subtitle_generation += 1
        self.subtitle_track.set([])
        self.video.set_caption('')
        self.caption_selector.blockSignals(True)
        self.caption_selector.clear()
        self.caption_selector.addItem('Subtitles off', None)
        self.caption_selector.blockSignals(False)

    def load_captions(self, subject, stream):
        self.clear_captions()
        generation = self.subtitle_generation
        key = self.playing_key
        def ready(data):
            if generation != self.subtitle_generation or key != self.playing_key:
                return
            self.caption_selector.blockSignals(True)
            self.caption_selector.clear()
            self.caption_selector.addItem('Subtitles off', None)
            for caption in data.get('captions') or []:
                self.caption_selector.addItem(caption.get('lanName') or caption.get('lan') or 'Subtitle', caption)
            language = data.get('language')
            for index in range(1, self.caption_selector.count()):
                if self.caption_selector.itemData(index).get('lan') == language:
                    self.caption_selector.setCurrentIndex(index)
                    break
            self.caption_selector.blockSignals(False)
            self.subtitle_track.set(data.get('cues') or [])
            self.position_changed(self.player.position())
            if data.get('error'):
                self.caption_selector.setToolTip(data['error'])
                self.status.setText('Video ready · Subtitles could not download. Choose a language to retry.')
            elif not data.get('captions'):
                self.caption_selector.setToolTip('No subtitles were returned for this episode by the service.')
            else:
                self.caption_selector.setToolTip('Downloaded subtitles are saved for this episode.')
        if self.state.get('subtitle_enabled', True):
            self.await_future(self._caption_future(key, subject, stream), ready,
                lambda message: self.caption_selector.setToolTip('Online subtitles unavailable. You can load an SRT file.'))
        else:
            descriptors = self.subtitle_store.descriptors(key)
            self.caption_selector.blockSignals(True)
            for caption in descriptors:
                self.caption_selector.addItem(caption.get('lanName') or caption.get('lan'), caption)
            self.caption_selector.blockSignals(False)
            if not descriptors:
                self.submit(lambda: self.api.captions(subject, stream['id']), ready, message='', failure=lambda message: None)

    def change_captions(self, index):
        self.subtitle_generation += 1
        generation = self.subtitle_generation
        self.subtitle_track.set([])
        self.video.set_caption('')
        caption = self.caption_selector.itemData(index)
        if not caption:
            self.state['subtitle_enabled'] = False
            self.persist()
            return
        self.state['subtitle_enabled'] = True
        self.state['subtitle_language'] = caption.get('lan')
        self.state.setdefault('subtitle_tracks', {})[self.playing_key] = caption.get('lan')
        self.persist()
        key = self.playing_key
        def ready(data):
            if generation != self.subtitle_generation:
                return
            self.subtitle_track.set(data.get('cues') or [])
            self.position_changed(self.player.position())
            language = data.get('language')
            if language:
                self.caption_selector.blockSignals(True)
                for row in range(1, self.caption_selector.count()):
                    if (self.caption_selector.itemData(row) or {}).get('lan') == language:
                        self.caption_selector.setCurrentIndex(row)
                        break
                self.caption_selector.blockSignals(False)
            if data.get('error'):
                self.caption_selector.setToolTip(data['error'])
                self.status.setText(data['error'])
            else:
                self.status.setText('Playing · ' + self.caption_selector.currentText() + ' subtitles' if self.player.isPlaying() else 'Subtitles ready')
        self.await_future(self._caption_future(key, self.playing_subject, self.current_stream, caption.get('lan')), ready, self.show_error)

    def open_subtitles(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Load subtitles', '', 'Subtitles (*.srt *.vtt)')
        if path:
            self.clear_captions()
            try:
                text = Path(path).read_text(encoding='utf-8-sig', errors='replace')
                cues = parse_subtitles(text)
                if self.playing_key:
                    self.subtitle_store.save_text(self.playing_key, 'local', {'lanName': Path(path).name}, text)
                    self.state.setdefault('subtitle_tracks', {})[self.playing_key] = 'local'
                    self.state['subtitle_enabled'] = True
                    self.persist()
                self.subtitle_track.set(cues)
                self.status.setText(f'{len(cues)} subtitle cues loaded from {Path(path).name}')
            except OSError as error:
                self.show_error(str(error))

    def adapt_quality(self):
        if time.monotonic() < getattr(self, 'seek_grace_until', 0):
            return
        if (self.stack.currentIndex() != 2 or self.quality.currentIndex() != 0 or not self.current_stream
                or not self.player.isPlaying() or len(self.streams) < 2 or self.auto_probe_running or time.monotonic() - self.last_auto_probe < 30):
            return
        self.auto_probe_running = True
        self.last_auto_probe = time.monotonic()
        original_url = self.current_stream['url']
        def done(speed):
            self.auto_probe_running = False
            if self.quality.currentIndex() != 0 or self.stack.currentIndex() != 2 or not self.player.isPlaying() or (self.current_stream or {}).get('url') != original_url or time.monotonic() < getattr(self, 'seek_grace_until', 0):
                return
            first_probe = not self.auto_bandwidth
            self.auto_bandwidth = speed if first_probe else .65 * self.auto_bandwidth + .35 * speed
            self.state['bandwidth_mbps'] = self.auto_bandwidth
            choices = [stream for stream in self.streams if int(stream.get('resolutions') or 0) <= 1080] or self.streams
            try:
                choices = matching_runtime(choices, float((self.current_stream or {}).get('duration') or self.player.duration() / 1000))
            except ValueError:
                return
            target = select_quality(choices, self.auto_bandwidth)
            if not target:
                return
            identity = target['url'] + str(target.get('resolutions'))
            self.auto_votes = self.auto_votes + 1 if identity == self.auto_candidate else 1
            self.auto_candidate = identity
            current_resolution = int(self.current_stream.get('resolutions') or 0)
            target_resolution = int(target.get('resolutions') or 0)
            current_identity = self.current_stream['url'] + str(self.current_stream.get('resolutions'))
            if identity != current_identity and (target_resolution < current_resolution or self.auto_votes >= 2 or first_probe):
                self.current_stream = target
                self.start_video(target['url'], self.player.position())
            self.quality.setItemText(0, 'Auto · ' + str(self.current_stream.get('resolutions') or '?') + 'p')
        headers = dict(self.current_stream.get('headers') or {})
        self.submit(lambda: measure_mbps(original_url, headers), done, message='',
                    failure=lambda message: setattr(self, 'auto_probe_running', False))

    def seek(self):
        self.seek_to(self.progress.value())

    def toggle_pause(self):
        if self.stack.currentIndex() == 2:
            self.player.pause() if self.player.isPlaying() else self.player.play()

    def toggle_fullscreen(self):
        if self.cinema and self.cinema.isVisible():
            self.cinema.leave()
        elif self.stack.currentIndex() == 2:
            if not self.cinema:
                self.cinema = CinemaWindow(self)
                self.video.cinema_stage = self.cinema
            self.cinema.enter()
        else:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def escape(self):
        if self.player_episode_panel.isVisible():self.close_player_episodes();return
        if (self.cinema and self.cinema.isVisible()) or self.isFullScreen():
            self.toggle_fullscreen()
        elif self.stack.currentIndex() == 2:
            self.leave_player()
        elif self.stack.currentIndex() == 1:
            self.stack.setCurrentIndex(0)

    def leave_player(self):
        self.volume_menu.hide()
        self.player_episode_panel.hide()
        self.next_up_panel.hide()
        if (self.cinema and self.cinema.isVisible()) or self.isFullScreen():
            self.toggle_fullscreen()
        self.save_progress()
        self.player.pause()
        if self.current_stream and self.playing_key:
            self.prepared_media = {'key': self.playing_key, 'remote': self.current_stream['url'],
                'local': self.player.source().toString(), 'position': self.player.position()}
        self.stack.setCurrentIndex(1 if self.current else 0)
        self.status.setText('Ready to resume')

    def stop_for_navigation(self):
        if hasattr(self,'volume_menu'):self.volume_menu.hide()
        if hasattr(self,'player_episode_panel'):self.player_episode_panel.hide()
        if hasattr(self,'next_up_panel'):self.next_up_panel.hide()
        self.capture_catalogue_view()
        if hasattr(self,'history_toolbar'):
            self.finish_history_selection()
            self.history_toolbar.hide()
        self.catalogue_kind = None
        if hasattr(self, 'catalogue_filter_panel'):
            self.catalogue_filter_panel.hide()
        self.play_intent += 1
        if getattr(self, 'prebuffering', False):
            self.player.stop()
            self.end_prebuffer()
        if self.cinema and self.cinema.isVisible():
            self.cinema.leave()
        self.hero_auto_play = ''
        if self.stack.currentIndex() == 2:
            self.save_progress()
            self.player.stop()
        self.request_generation += 1

    def toggle_saved(self):
        key = str(self.current['subjectId'])
        if key in self.state['saved']:
            del self.state['saved'][key]
            self.save.setText('My list')
        else:
            self.state['saved'][key] = self.current
            self.save.setText('Saved')
        self.persist()

    def show_saved(self):
        self.stop_for_navigation()
        from fluent_ui import set_nav
        set_nav(self, 'saved')
        self.hero.hide()
        self.page_subtitle.setText('The stories you want to come back to.')
        self.heading.setText('Your list')
        self.category.hide()
        self.more.hide()
        self.show_items(list(self.state['saved'].values()))

    def show_history(self):
        self.stop_for_navigation()
        from fluent_ui import set_nav
        set_nav(self, 'history')
        self.hero.hide()
        self.page_subtitle.setText('A little more of the story. Right where you left off.')
        self.heading.setText('Continue watching')
        self.category.hide()
        self.more.hide()
        history = sorted(self.state['history'].values(), key=lambda item: item.get('updated', 0), reverse=True)
        self.show_items([item['subject'] for item in history])
        self.history_toolbar.show()
        self.update_history_selection()

    def catalogue_clicked(self,index):
        if not self.history_editing:self.open_detail(index.data(Qt.UserRole))

    def catalogue_activated(self,index):
        if self.history_editing:
            from PySide6.QtCore import QItemSelectionModel
            self.grid.selectionModel().select(index,QItemSelectionModel.Toggle)
        else:self.open_detail(index.data(Qt.UserRole))

    def begin_history_selection(self):
        self.history_editing=True
        self.grid.setSelectionMode(QListView.MultiSelection)
        self.grid.clearSelection();self.update_history_selection();self.grid.setFocus()

    def finish_history_selection(self):
        self.history_editing=False
        if hasattr(self,'grid'):
            self.grid.setSelectionMode(QListView.SingleSelection)
            self.grid.clearSelection();self.update_history_selection()

    def update_history_selection(self,*_):
        if not hasattr(self,'history_select'):return
        selected=len(self.grid.selectionModel().selectedRows()) if self.history_editing else 0
        self.history_select.setVisible(not self.history_editing)
        for button in (self.history_all,self.history_remove,self.history_done):button.setVisible(self.history_editing)
        self.history_remove.setText(f'Remove selected ({selected})')
        self.history_remove.setEnabled(selected>0)
        self.history_all.setText('Clear selection' if selected and selected==self.catalog_model.rowCount() else 'Select all')
        self.history_undo_button.setVisible(bool(self.history_undo))
        self.grid.viewport().update()

    def select_all_history(self):
        if len(self.grid.selectionModel().selectedRows())==self.catalog_model.rowCount():self.grid.clearSelection()
        else:self.grid.selectAll()

    def remove_selected_history(self):
        identities={str(index.data(Qt.UserRole)['subjectId']) for index in self.grid.selectionModel().selectedRows()}
        if not identities:return
        removed={key:value for key,value in self.state['history'].items() if str((value.get('subject') or {}).get('subjectId')) in identities}
        for key in removed:self.state['history'].pop(key,None)
        if not self.persist():
            self.state['history'].update(removed);return
        self.history_undo=removed
        playing=str((self.playing_subject or {}).get('_audio_base_id') or (self.playing_subject or {}).get('subjectId') or '')
        if playing in identities:
            self.playing_key='';self.last_progress_checkpoint=None;self.prepared_media=None
        self.show_history()
        self.status.setText(f'Removed {len(identities)} title(s) from Continue watching. Undo is available.')

    def undo_history_removal(self):
        for key,value in self.history_undo.items():self.state['history'].setdefault(key,value)
        if not self.persist():return
        self.history_undo={};self.show_history();self.status.setText('Continue watching restored.')

    def save_progress(self):
        if self.resume_position or not self.playing_key or not self.playing_subject:
            return
        position, duration = self.player.position(), self.player.duration()
        checkpoint = self.last_progress_checkpoint
        if checkpoint and checkpoint[0] == self.playing_key:
            if position <= 0 or self.stack.currentIndex() != 2:
                position, duration = checkpoint[1:]
        elif self.stack.currentIndex() != 2:
            return
        if position <= 0:
            return
        history_key = self.playing_key
        history_subject = self.playing_subject
        if self.playing_subject.get('_audio_base_id'):
            history_key = self.playing_subject['_audio_base_id'] + ':' + ':'.join(self.playing_key.rsplit(':', 2)[1:])
            history_subject = {**self.playing_subject, 'subjectId': self.playing_subject['_audio_base_id']}
        self.state['history'][history_key] = {'subject': history_subject,
            'completed': bool(self.end_handled),
            'position': position, 'duration': duration or int(float((self.current_stream or {}).get('duration') or 0) * 1000), 'updated': time.time(),
            'audio_subject_id': str(self.playing_subject['subjectId'])}
        self.persist()

    def persist(self):
        try:
            self.library_store.save(self.state)
            return True
        except (OSError, ValueError) as error:
            self.status.setText('Could not save your library. Check free disk space and folder permissions; MovieBox will retry.')
            self.status.setToolTip(str(error))
            return False

    def open_local(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open a video', '', 'Video files (*.mp4 *.mkv *.webm *.mov *.avi);;All files (*)')
        if path:
            self.playback_return_view = 0
            self.save_progress()
            self.playing_subject, self.playing_key = None, ''
            self.current_stream = None
            self.preview_limit = 0
            self.quality.clear()
            self.clear_captions()
            self.now_title.setText(Path(path).name)
            self.start_video(QUrl.fromLocalFile(path).toString())

    def download_current(self):
        if not self.current_stream or not self.playing_subject or self.preview_limit:
            return
        import re
        title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', self.playing_subject['title'])[:140].rstrip('. ')
        quality = self.current_stream.get('resolutions') or 'video'
        suggested = Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)) / 'MovieBox' / f'{title} - {self.playing_key.replace(":", "-")} - {quality}p.mp4'
        path, _ = QFileDialog.getSaveFileName(self, 'Save this video', str(suggested), 'MP4 video (*.mp4)')
        if not path:
            return
        if any(d.target == Path(path) and d.status in ('Starting', 'Downloading') for d in self.downloads):
            self.show_error('This file is already downloading.')
            return
        headers = self.current_stream.get('headers') or {'User-Agent': 'Mozilla/5.0'}
        download = Download(self.current_stream['url'], Path(path), headers)
        self.downloads.append(download)
        self.download_pool.submit(download.run)
        self.status.setText('Download started in the background.')

    def update_downloads(self):
        complete = [str(d.target) for d in self.downloads if d.status == 'Complete']
        previous = self.state.get('downloads', [])
        if any(path not in previous for path in complete):
            self.state['downloads'] = list(dict.fromkeys(previous + complete))
            self.persist()
        if self.stack.currentIndex() != 3:
            return
        self.download_list.clear()
        for task in self.downloads:
            percent = f'{task.received / task.total * 100:.0f}%' if task.total else f'{task.received / 1048576:.1f} MB'
            item = QListWidgetItem(f'{task.target.name}\n{task.status} · {percent}')
            item.setData(Qt.UserRole, str(task.target) if task.status == 'Complete' else '')
            self.download_list.addItem(item)
        listed = {str(d.target) for d in self.downloads}
        for path in self.state.get('downloads', []):
            if path not in listed and Path(path).is_file():
                item = QListWidgetItem(Path(path).name + '\nComplete')
                item.setData(Qt.UserRole, path)
                self.download_list.addItem(item)
        has_downloads = self.download_list.count() > 0
        self.download_list.setVisible(has_downloads)
        self.download_empty.setVisible(not has_downloads)

    def show_downloads(self):
        self.stop_for_navigation()
        from fluent_ui import set_nav
        set_nav(self, 'downloads')
        self.stack.setCurrentIndex(3)
        self.update_downloads()
        self.status.setText('Downloads stay on this PC.')

    def pause_downloads(self):
        for task in self.downloads:
            task.cancelled.set()

    def open_download(self, item):
        path = item.data(Qt.UserRole)
        if path and Path(path).is_file():
            self.playback_return_view = 3
            self.playing_subject, self.playing_key, self.current_stream = None, '', None
            self.preview_limit = 0
            self.clear_captions()
            self.quality.clear()
            self.now_title.setText(Path(path).name)
            self.start_video(QUrl.fromLocalFile(path).toString())

    def closeEvent(self, event):
        self.volume_menu.hide()
        self.player_episode_panel.hide()
        self.closing=True;self.request_generation+=1;self.play_intent+=1
        self.next_up_panel.hide()
        self.capture_catalogue_view()
        self.catalogue_cache.flush()
        self.update_timer.stop()
        self.update_pool.shutdown(wait=False, cancel_futures=True)
        if self.cinema and self.cinema.isVisible():
            self.cinema.leave()
        self.save_progress()
        self.player.stop()
        self.pause_downloads()
        self.download_pool.shutdown(wait=False, cancel_futures=True)
        self.download_timer.stop()
        self.adaptive_timer.stop()
        self.bridge.close()
        self.art.timer.stop()
        self.job_timer.stop()
        self.art_pool.shutdown(wait=False, cancel_futures=True)
        self.pool.shutdown(wait=False, cancel_futures=True)
        event.accept()

    def capture_catalogue_view(self):
        if not getattr(self,'catalogue_kind',None) or not getattr(self,'active_catalogue_cache_key',''):
            return
        if self.catalogue_pending_refresh_key==self.active_catalogue_cache_key:return
        entry=self.catalogue_cache.get(self.active_catalogue_cache_key)
        if entry and hasattr(self,'grid'):
            entry['scroll']=self.grid.verticalScrollBar().value()
            entry['row']=max(0,self.grid.currentIndex().row())
            self.catalogue_cache.put(self.active_catalogue_cache_key,entry)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'hero'):
            self.hero.set_compact(self.height() < 820)
            home_selected = self.nav_buttons.get('home') and self.nav_buttons['home'].isChecked()
            self.hero.setVisible(bool(home_selected) and self.height() >= 700)
            compact = self.width() < 1180
            self.detail_cover.setFixedSize(210, 315) if compact else self.detail_cover.setFixedSize(255, 382)
            self.detail_title.setStyleSheet('font-size:28px' if compact else 'font-size:33px')
            self.position_next_up()
            self.position_player_episodes()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, 'video'):
            self.video.position_caption()
            self.position_next_up()
            self.position_player_episodes()



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--output', default='verification')
    parser.add_argument('--media-test', default='')
    args = parser.parse_args()
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Local.MovieBox.Desktop')
    except (AttributeError, OSError):
        pass
    app = QApplication(sys.argv[:1])
    app.setApplicationName('MovieBox Desktop')
    app.setOrganizationName('Local Desktop Builds')
    icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets' / 'app.ico'
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyle('Fusion')
    from fluent_ui import stylesheet, system_is_dark
    from themes import initial_theme
    app.setStyleSheet(stylesheet(initial_theme(load_state(), system_is_dark())))
    window = Window()
    window.show()
    if args.smoke_test:
        from smoke import SmokeTest
        window.smoke = SmokeTest(window, Path(args.output), args.media_test)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
