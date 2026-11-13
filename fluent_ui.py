"""Fluent-inspired native Windows shell. All browsing and playback stay native Qt."""
from __future__ import annotations
import ctypes
from pathlib import Path
import sys
import winreg
from PySide6.QtCore import Qt, QSize, QRectF, QUrl, QTimer, QBuffer, QByteArray, QIODevice, QPoint
from PySide6.QtGui import (QColor, QPainter, QPixmap, QFont, QIcon, QLinearGradient,
    QPainterPath, QImageReader, QShortcut, QKeySequence)
from PySide6.QtWidgets import (QApplication, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QListView, QListWidget, QSlider,
    QSpinBox, QCheckBox, QStackedWidget, QSizePolicy, QDialog, QFileDialog, QScrollArea, QMenu, QWidgetAction)
from PySide6.QtSvg import QSvgRenderer
from interactions import SeekSlider, FluentComboBox


ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
ASSETS = ROOT / 'assets'
ACCENT = '#48e6b0'
PATHS = {
    'home': '<path d="M3 10.5 12 3l9 7.5V21h-6v-7H9v7H3z"/>',
    'movie': '<rect x="3" y="5" width="18" height="15" rx="3"/><path d="M3 10h18M7 5l3 5m4-5 3 5"/>',
    'series': '<rect x="3" y="6" width="18" height="14" rx="3"/><path d="m8 2 4 4 4-4"/>',
    'anime': '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
    'bookmark': '<path d="M6 4h12v17l-6-4-6 4z"/>',
    'history': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'download': '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
    'folder': '<path d="M3 6h7l2 2h9v12H3z"/>',
    'settings': '<path d="m10 3-.6 2.3-2 .8L5.3 5 3 9l1.8 1.6v2.8L3 15l2.3 4 2.1-1.1 2 .8L10 21h4l.6-2.3 2-.8 2.1 1.1 2.3-4-1.8-1.6v-2.8L21 9l-2.3-4-2.1 1.1-2-.8L14 3z"/><circle cx="12" cy="12" r="3"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    'search': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    'back': '<path d="m10 4-8 8 8 8M2 12h20"/>',
    'play': '<path d="m8 4 13 8-13 8z"/>',
    'pause': '<path d="M8 5v14M16 5v14"/>',
    'fullscreen': '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5"/>',
    'next': '<path d="m5 4 12 8-12 8zM20 4v16"/>',
    'subtitle': '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="M5 12h5m3 0h6M5 16h9m3 0h2"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
}


def icon(name, color=None, size=20):
    if color is None:
        color = '#c2c9d5' if QApplication.instance().property('movieboxDark') else '#516273'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{PATHS.get(name, PATHS["movie"])}</svg>'
    renderer = QSvgRenderer(svg.encode())
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def system_is_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return not bool(winreg.QueryValueEx(key, 'AppsUseLightTheme')[0])
    except OSError:
        return True


def apply_window_material(window, dark=True):
    try:
        hwnd = int(window.winId())
        for attribute, value in [(20, int(dark)), (33, 2), (38, 2),
                                 (35, 0x001A1410 if dark else 0x00F7F5F2)]:
            number = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attribute,
                ctypes.byref(number), ctypes.sizeof(number))
    except (AttributeError, OSError):
        pass


def refresh_theme(window, dark):
    QApplication.instance().setStyleSheet(stylesheet(dark))
    for widget in window.findChildren(QPushButton):
        glyph = widget.property('fluentGlyph')
        if glyph:
            widget.setIcon(icon(glyph, '#08251a' if widget.property('fluentPrimary') else None))
    window.search_action.setIcon(icon('search'))
    apply_window_material(window, dark)
    window.grid.viewport().update()


def stylesheet(dark=True):
    p = ({'base':'#0b0f15','panel':'#121820','surface':'#1a222d','hover':'#232e3b',
          'text':'#f0f3f8','secondary':'#9ba9bd','line':'#2a3543','field':'#19212c','select':'#233932'}
         if dark else
         {'base':'#eef1f6','panel':'#f9fafc','surface':'#ffffff','hover':'#e9edf4',
          'text':'#182431','secondary':'#647286','line':'#d9e0e9','field':'#ffffff','select':'#d7f3e8'})
    app = QApplication.instance()
    app.setProperty('movieboxDark', dark)
    css = '''
    QWidget{background:transparent;color:TEXT;font-family:"Segoe UI Variable Text","Segoe UI";font-size:13px}
    QWidget#appRoot{background:BASE}
    QFrame#sidebar{background:BASE;border:none}
    QFrame#contentPanel{background:PANEL;border:1px solid LINE;border-radius:18px}
    QLabel#brandName{font-family:"Segoe UI Variable Display","Segoe UI";font-size:21px;font-weight:700}
    QLabel#brandEdition{color:SECONDARY;font-size:10px;letter-spacing:1.2px}
    QLabel#sectionLabel{color:SECONDARY;font-size:10px;font-weight:600;letter-spacing:1px;padding:16px 16px 7px}
    QLabel#eyebrow{color:SECONDARY;font-size:11px;letter-spacing:1.4px;font-weight:600}
    QLabel#heading{font-family:"Segoe UI Variable Display","Segoe UI";font-size:29px;font-weight:600}
    QLabel#muted,QLabel#pageSubtitle{color:SECONDARY;font-size:12px}
    QLabel#breadcrumb{color:SECONDARY;font-size:12px}
    QLabel#detailTitle{font-family:"Segoe UI Variable Display","Segoe UI";font-size:33px;font-weight:650}
    QLabel#nowTitle{font-size:17px;font-weight:600}
    QPushButton{background:SURFACE;border:1px solid LINE;border-radius:8px;padding:10px 15px;font-weight:500}
    QPushButton:hover{background:HOVER;border-color:SECONDARY}
    QPushButton:pressed{background:SELECT}
    QPushButton:focus{border-color:#48e6b0}
    QPushButton:disabled{color:SECONDARY;background:transparent;border-color:LINE}
    QPushButton#primary{background:#48e6b0;color:#08251a;border:1px solid #65efc0;font-weight:600}
    QPushButton#primary:hover{background:#78f0c6}
    QPushButton#primary:pressed{background:#2fcb96}
    QPushButton#navItem{background:transparent;border:1px solid transparent;border-radius:8px;text-align:left;padding:12px 17px;font-size:14px}
    QPushButton#navItem:hover{background:HOVER;border-color:transparent}
    QPushButton#navItem:checked{background:SELECT;border-color:transparent;font-weight:600}
    QPushButton#quiet{background:transparent;border:1px solid transparent;color:SECONDARY}
    QPushButton#quiet:hover{background:HOVER;color:TEXT}
    QPushButton#roundTool{padding:10px;min-width:19px;max-width:26px;background:SURFACE}
    QLineEdit{background:FIELD;border:1px solid LINE;border-bottom:2px solid SECONDARY;border-radius:8px;padding:10px 14px;selection-background-color:#2c9c7b}
    QLineEdit:focus{border-bottom-color:#48e6b0}
    QComboBox{background:FIELD;border:1px solid LINE;border-radius:8px;padding:9px 30px 9px 12px}
    QComboBox:hover{background:HOVER}
    QComboBox::drop-down{border:0;width:24px}
    QComboBox QAbstractItemView{background:SURFACE;color:TEXT;border:1px solid LINE;padding:5px;selection-background-color:SELECT;outline:0}
    QComboBox QAbstractItemView::item{min-height:32px;padding:2px 12px;border:0;border-radius:6px}
    QComboBox QAbstractItemView::item:hover{background:HOVER}
    QComboBox QAbstractItemView::item:selected{background:SELECT;color:TEXT}
    QSpinBox{background:FIELD;border:1px solid LINE;border-radius:8px;padding:8px;min-width:62px}
    QSpinBox::up-button,QSpinBox::down-button{background:transparent;border:0;width:17px}
    QAbstractItemView{border:0;outline:0;background:transparent;selection-background-color:SELECT}
    QListWidget::item{background:SURFACE;border:1px solid LINE;border-radius:10px;padding:16px;margin:4px}
    QListWidget::item:hover{background:HOVER}
    QScrollBar:vertical{background:transparent;width:8px;margin:4px 0}
    QScrollBar::handle:vertical{background:LINE;border-radius:4px;min-height:36px}
    QScrollBar::handle:vertical:hover{background:SECONDARY}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
    QSlider::groove:horizontal{background:LINE;height:4px;border-radius:2px}
    QSlider::sub-page:horizontal{background:#48e6b0;border-radius:2px}
    QSlider::handle:horizontal{background:#48e6b0;border:3px solid SURFACE;width:13px;margin:-6px 0;border-radius:9px}
    QCheckBox{spacing:8px;color:SECONDARY}
    QCheckBox::indicator{width:16px;height:16px;background:FIELD;border:1px solid LINE;border-radius:4px}
    QCheckBox::indicator:checked{background:#48e6b0;border-color:#48e6b0}
    QDialog{background:PANEL}
    QToolTip{background:SURFACE;color:TEXT;border:1px solid LINE;padding:8px;border-radius:6px}
    QMenu{background:SURFACE;color:TEXT;border:1px solid LINE;padding:5px}
    QMenu::item{padding:8px 26px;border-radius:6px}
    QMenu::item:selected{background:SELECT}
    QFrame#detailCard,QFrame#controlBar{background:SURFACE;border:1px solid LINE;border-radius:16px}
    QListWidget#episodeCards::item{padding:8px;margin:3px;background:SURFACE;border:1px solid LINE;border-radius:8px}
    QListWidget#episodeCards::item:selected{background:SELECT;border-color:#48e6b0;color:TEXT}
    '''
    for name, value in p.items():
        css = css.replace(name.upper(), value)
    arrow = (ASSETS / ('chevron-down.svg' if dark else 'chevron-down-light.svg')).as_posix()
    up = (ASSETS / ('chevron-up.svg' if dark else 'chevron-up-light.svg')).as_posix()
    check = (ASSETS / 'check.svg').as_posix()
    css += f'''QComboBox::down-arrow{{image:url("{arrow}");width:12px;height:12px}}
        QSpinBox::up-arrow{{image:url("{up}");width:10px;height:10px}}
        QSpinBox::down-arrow{{image:url("{arrow}");width:10px;height:10px}}
        QCheckBox::indicator:checked{{image:url("{check}")}}'''
    return css


class NavButton(QPushButton):
    def __init__(self, text, glyph, callback, *, selectable=True):
        super().__init__('  ' + text)
        self.setObjectName('navItem')
        self.setIcon(icon(glyph))
        self.setProperty('fluentGlyph', glyph)
        self.setIconSize(QSize(19, 19))
        self.setCheckable(selectable)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(45)
        self.clicked.connect(callback)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(QRectF(0, self.height() / 2 - 10, 3, 20), 1.5, 1.5)


def action(text, callback=None, glyph=None, *, primary=False, quiet=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.PointingHandCursor)
    if glyph:
        widget.setIcon(icon(glyph, '#08251a' if primary else None))
        widget.setProperty('fluentGlyph', glyph)
        widget.setProperty('fluentPrimary', primary)
        widget.setIconSize(QSize(18, 18))
    if primary:
        widget.setObjectName('primary')
    elif quiet:
        widget.setObjectName('quiet')
    if callback:
        widget.clicked.connect(callback)
    return widget


class HeroCard(QWidget):
    def __init__(self, window, fetch_bytes):
        super().__init__()
        self.window, self.fetch_bytes = window, fetch_bytes
        self.image = QPixmap()
        self.loading_logo = QIcon(str(ASSETS / 'moviebox-logo.svg')).pixmap(128, 144)
        self.subject = None
        self.generation = 0
        self.setMinimumHeight(248)
        self.setMaximumHeight(270)
        content = QVBoxLayout(self)
        content.setContentsMargins(28, 23, 28, 23)
        content.setSpacing(9)
        eyebrow = QLabel('IN THE SPOTLIGHT')
        eyebrow.setStyleSheet('color:#9ceacb;font-size:10px;font-weight:650;letter-spacing:2px')
        content.addWidget(eyebrow)
        self.title = QLabel('A world of stories.\nOne beautiful place.')
        self.title.setTextFormat(Qt.PlainText)
        self.title.setWordWrap(True)
        self.title.setMaximumWidth(600)
        self.title.setStyleSheet('color:white;font-family:"Segoe UI Variable Display","Segoe UI";font-size:31px;font-weight:650;background:transparent')
        content.addWidget(self.title)
        self.meta = QLabel('Movies. Series. Your next favorite.')
        self.meta.setStyleSheet('color:#c4ced9;font-size:12px')
        content.addWidget(self.meta)
        content.addStretch()
        actions = QHBoxLayout()
        self.explore = action('Watch now', self.open, 'play', primary=True)
        self.explore.setFixedWidth(145)
        actions.addWidget(self.explore)
        self.save = action('My list', self.save_subject, 'bookmark')
        self.save.setStyleSheet('QPushButton{background:rgba(255,255,255,20);color:white;border:1px solid rgba(255,255,255,50)}QPushButton:hover{background:rgba(255,255,255,38)}')
        actions.addWidget(self.save)
        actions.addStretch()
        content.addLayout(actions)

    def set_compact(self, compact):
        if getattr(self, 'compact', None) == compact:
            return
        self.compact = compact
        self.setFixedHeight(172 if compact else 248)
        self.layout().setContentsMargins(24, 15, 24, 15) if compact else self.layout().setContentsMargins(28, 23, 28, 23)
        self.layout().setSpacing(6 if compact else 9)
        self.layout().itemAt(0).widget().setVisible(not compact)
        self.title.setStyleSheet('color:white;font-family:"Segoe UI Variable Display","Segoe UI";font-size:' + ('24' if compact else '31') + 'px;font-weight:650;background:transparent')

    def set_subject(self, subject):
        if self.subject and self.subject.get('subjectId') == subject.get('subjectId'):
            return
        self.subject = subject
        self.generation += 1
        generation = self.generation
        title = subject.get('title') or 'Find your next favorite.'
        self.title.setText(title[:100])
        self.meta.setText('  ·  '.join(str(x) for x in [str(subject.get('releaseDate') or '')[:4],
            subject.get('genre', '').replace(',', ' · '), ('IMDb ' + str(subject['imdbRatingValue'])) if subject.get('imdbRatingValue') else ''] if x))
        url = (subject.get('stills') or {}).get('url') or ((subject.get('trailer') or {}).get('cover') or {}).get('url') or (subject.get('cover') or {}).get('url')
        if not url:
            return
        def load():
            buffer = QBuffer()
            buffer.setData(QByteArray(self.fetch_bytes(url)))
            buffer.open(QIODevice.ReadOnly)
            reader = QImageReader(buffer)
            size = reader.size()
            if size.isValid():
                size.scale(QSize(1400, 900), Qt.KeepAspectRatio)
                reader.setScaledSize(size)
            return reader.read()
        def ready(image):
            if generation == self.generation and not image.isNull():
                self.image = QPixmap.fromImage(image)
                self.update()
        self.window.submit(load, ready, message='', failure=lambda message: None)

    def open(self):
        if self.subject:
            self.window.hero_auto_play = str(self.subject['subjectId'])
            self.window.open_detail(self.subject)

    def save_subject(self):
        if self.subject:
            key = str(self.subject['subjectId'])
            if key in self.window.state['saved']:
                del self.window.state['saved'][key]
                self.save.setText('My list')
            else:
                self.window.state['saved'][key] = self.subject
                self.save.setText('Saved')
            self.window.persist()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 18, 18)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor('#15242a'))
        if not self.image.isNull():
            target = self.image.size().scaled(self.size(), Qt.KeepAspectRatioByExpanding)
            source = QRectF((self.image.width() - self.width() * self.image.width() / target.width()) / 2,
                            (self.image.height() - self.height() * self.image.height() / target.height()) / 2,
                            self.width() * self.image.width() / target.width(), self.height() * self.image.height() / target.height())
            painter.drawPixmap(QRectF(self.rect()), self.image, source)
        else:
            painter.setOpacity(.18)
            painter.drawPixmap(self.width() - 235, (self.height() - 144) // 2, self.loading_logo)
            painter.setOpacity(1)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor(9, 21, 25, 250))
        gradient.setColorAt(.45, QColor(9, 21, 25, 208))
        gradient.setColorAt(.78, QColor(9, 21, 25, 55))
        gradient.setColorAt(1, QColor(9, 21, 25, 12))
        painter.fillRect(self.rect(), gradient)
        vertical = QLinearGradient(0, 0, 0, self.height())
        vertical.setColorAt(0, QColor(0, 0, 0, 0))
        vertical.setColorAt(1, QColor(0, 7, 12, 90))
        painter.fillRect(self.rect(), vertical)
        painter.setClipping(False)
        painter.setPen(QColor(255, 255, 255, 22))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 18, 18)


def set_nav(window, name):
    for key, widget in window.nav_buttons.items():
        widget.setChecked(key == name)
    if hasattr(window, 'breadcrumb'):
        label = {'home':'Discover','movies':'Movies','series':'TV series','anime':'Anime',
                 'saved':'My list','history':'Continue watching','downloads':'Downloads'}.get(name, 'Search')
        window.breadcrumb.setText('MovieBox  /  ' + label)


def browse_kind(window, name):
    window.stop_for_navigation()
    set_nav(window, name)
    window.hero.hide()
    window.category.hide()
    window.more.hide()
    window.heading.setText({'movies':'Movies','series':'TV series','anime':'Anime'}[name])
    window.page_subtitle.setText('Picked from your MovieBox catalog')
    items = [item for row in window.sections.values() for item in row]
    if name == 'movies':
        items = [item for item in items if item.get('subjectType') == 1]
    elif name == 'series':
        items = [item for item in items if item.get('subjectType') == 2]
    else:
        items = [item for item in items if any(term in item.get('genre', '').lower() for term in ('anime','animation'))]
    window.show_items(items)


def open_settings(window):
    dialog = QDialog(window)
    dialog.setWindowTitle('MovieBox settings')
    dialog.setMinimumWidth(470)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(18)
    title = QLabel('Make it yours')
    title.setObjectName('heading')
    layout.addWidget(title)
    layout.addWidget(QLabel('Appearance'))
    appearance = FluentComboBox()
    appearance.addItems(['Dark', 'Light', 'Follow Windows'])
    modes = ['dark','light','system']
    appearance.setCurrentIndex(modes.index(window.state.get('appearance', 'dark')) if window.state.get('appearance', 'dark') in modes else 0)
    def change(index):
        mode = modes[index]
        window.state['appearance'] = mode
        window.persist()
        dark = mode == 'dark' or (mode == 'system' and system_is_dark())
        refresh_theme(window, dark)
    appearance.currentIndexChanged.connect(change)
    layout.addWidget(appearance)
    layout.addWidget(QLabel('Subtitle text size'))
    size = QSpinBox()
    size.setRange(16, 44)
    size.setSuffix(' px')
    size.setValue(int(window.state.get('subtitle_size', 24)))
    def set_size(value):
        window.state['subtitle_size'] = value
        window.persist()
        window.video.caption.setStyleSheet(f'background:rgba(0,0,0,180);color:white;font-size:{value}px;font-weight:600;padding:8px;border-radius:7px')
    size.valueChanged.connect(set_size)
    layout.addWidget(size)
    updates = QCheckBox('Notify me about optional MovieBox updates')
    updates.setChecked(window.state['update_notifications'].get('enabled', True))
    updates.toggled.connect(window.configure_optional_updates)
    layout.addWidget(updates)
    check_updates = action('Check for updates', lambda: window.check_optional_updates(force=True))
    check_updates.setEnabled(updates.isChecked())
    updates.toggled.connect(check_updates.setEnabled)
    layout.addWidget(check_updates)
    hint = QLabel('F11 · Fullscreen     Esc · Back     Ctrl+K · Search\nPlayback quality follows available sources and your connection.')
    hint.setWordWrap(True)
    hint.setObjectName('muted')
    layout.addWidget(hint)
    layout.addWidget(action('Done', dialog.accept, primary=True), 0, Qt.AlignRight)
    QTimer.singleShot(0, lambda: apply_window_material(dialog, bool(QApplication.instance().property('movieboxDark'))))
    dialog.exec()


def build_ui(w, catalog_model_type, delegate_type, video_type, fetch_bytes):
    w.setWindowTitle('MovieBox')
    available = QApplication.primaryScreen().availableGeometry()
    w.resize(min(1440, available.width() - 30), max(640, min(940, available.height() - 40)))
    w.setMinimumSize(1080, 640)
    root = QWidget()
    root.setObjectName('appRoot')
    w.setCentralWidget(root)
    shell = QHBoxLayout(root)
    shell.setContentsMargins(10, 10, 12, 12)
    shell.setSpacing(10)
    sidebar = QFrame()
    w.sidebar = sidebar
    w.outer_layout = shell
    sidebar.setObjectName('sidebar')
    sidebar.setFixedWidth(212)
    side = QVBoxLayout(sidebar)
    side.setContentsMargins(6, 13, 6, 12)
    side.setSpacing(4)
    brand_row = QHBoxLayout()
    brand_row.setContentsMargins(13, 0, 5, 20)
    brand = QLabel()
    brand.setPixmap(QIcon(str(ASSETS / 'moviebox-logo.svg')).pixmap(32, 36))
    brand.setFixedSize(36, 40)
    brand_row.addWidget(brand)
    brand_text = QVBoxLayout()
    brand_text.setSpacing(0)
    name = QLabel('MovieBox')
    name.setObjectName('brandName')
    edition = QLabel('FOR WINDOWS')
    edition.setObjectName('brandEdition')
    brand_text.addWidget(name)
    brand_text.addWidget(edition)
    brand_row.addLayout(brand_text)
    brand_row.addStretch()
    side.addLayout(brand_row)
    w.nav_buttons = {}
    entries = [('home','Home','home', w.show_discover),
               ('movies','Movies','movie',lambda: browse_kind(w,'movies')),
               ('series','TV series','series',lambda: browse_kind(w,'series')),
               ('anime','Anime','anime',lambda: browse_kind(w,'anime'))]
    for key, text, glyph, callback in entries:
        item = NavButton(text, glyph, callback)
        w.nav_buttons[key] = item
        side.addWidget(item)
    library_label = QLabel('YOUR LIBRARY')
    library_label.setObjectName('sectionLabel')
    side.addWidget(library_label)
    for key, text, glyph, callback in [('saved','My list','bookmark',w.show_saved),
            ('history','Continue watching','history',w.show_history),('downloads','Downloads','download',w.show_downloads)]:
        item = NavButton(text, glyph, callback)
        w.nav_buttons[key] = item
        side.addWidget(item)
    side.addStretch()
    side.addWidget(NavButton('Open a video', 'folder', w.open_local, selectable=False))
    side.addWidget(NavButton('Settings', 'settings', lambda: open_settings(w), selectable=False))
    w.sign_in = NavButton('Account' if w.api.account_token else 'Sign in', 'user', w.open_account, selectable=False)
    side.addWidget(w.sign_in)
    w.connection = QLabel('Connecting…')
    w.connection.setObjectName('muted')
    w.connection.setContentsMargins(18, 14, 0, 0)
    side.addWidget(w.connection)
    shell.addWidget(sidebar)

    column = QVBoxLayout()
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(13)
    w.top_bar = QWidget()
    top = QHBoxLayout(w.top_bar)
    top.setContentsMargins(10, 6, 5, 0)
    crumb = QLabel('MovieBox  /  Discover')
    w.breadcrumb = crumb
    crumb.setObjectName('breadcrumb')
    top.addWidget(crumb, 1)
    w.search = QLineEdit()
    w.search.setObjectName('searchBox')
    w.search.setPlaceholderText('Search movies, series, anime')
    w.search.setClearButtonEnabled(True)
    w.search.setMinimumWidth(290)
    w.search.setMaximumWidth(400)
    w.search_action = w.search.addAction(icon('search'), QLineEdit.LeadingPosition)
    w.search.returnPressed.connect(w.run_search)
    top.addWidget(w.search, 1)
    search_go = action('', w.run_search, 'search')
    search_go.setObjectName('roundTool')
    search_go.setToolTip('Search · Enter')
    top.addWidget(search_go)
    column.addWidget(w.top_bar)
    content = QFrame()
    content.setObjectName('contentPanel')
    content_layout = QVBoxLayout(content)
    w.content_layout = content_layout
    content_layout.setContentsMargins(23, 22, 23, 10)
    content_layout.setSpacing(10)
    w.stack = QStackedWidget()
    content_layout.addWidget(w.stack, 1)
    w.status = QLabel('Getting everything ready…')
    w.status.setObjectName('muted')
    w.status.setTextFormat(Qt.PlainText)
    w.status.setWordWrap(True)
    w.status.setContentsMargins(4, 4, 0, 2)
    content_layout.addWidget(w.status)
    column.addWidget(content, 1)
    shell.addLayout(column, 1)

    catalog = QWidget()
    cat = QVBoxLayout(catalog)
    cat.setContentsMargins(0, 0, 0, 0)
    cat.setSpacing(17)
    w.hero = HeroCard(w, fetch_bytes)
    cat.addWidget(w.hero)
    row = QHBoxLayout()
    titles = QVBoxLayout()
    titles.setSpacing(4)
    w.heading = QLabel('Find your next favorite')
    w.heading.setObjectName('heading')
    w.page_subtitle = QLabel('Stories worth making time for.')
    w.page_subtitle.setObjectName('pageSubtitle')
    titles.addWidget(w.heading)
    titles.addWidget(w.page_subtitle)
    row.addLayout(titles, 1)
    w.category = FluentComboBox()
    w.category.setMinimumWidth(210)
    w.category.view().setMinimumWidth(260)
    w.category.currentTextChanged.connect(w.category_changed)
    row.addWidget(w.category, 0, Qt.AlignVCenter)
    w.more = action('Load more', w.load_more)
    w.more.hide()
    row.addWidget(w.more)
    cat.addLayout(row)
    w.catalog_model = catalog_model_type()
    w.grid = QListView()
    w.grid.setModel(w.catalog_model)
    w.grid.setViewMode(QListView.IconMode)
    w.grid.setResizeMode(QListView.Adjust)
    w.grid.setMovement(QListView.Static)
    w.grid.setSpacing(8)
    w.grid.setUniformItemSizes(True)
    w.grid.setMouseTracking(True)
    w.grid.setVerticalScrollMode(QListView.ScrollPerPixel)
    w.poster_delegate = delegate_type(w.art, w.grid)
    w.grid.setItemDelegate(w.poster_delegate)
    w.grid.clicked.connect(lambda index: w.open_detail(index.data(Qt.UserRole)))
    w.grid.activated.connect(lambda index: w.open_detail(index.data(Qt.UserRole)))
    w.art.changed.connect(w.grid.viewport().update)
    cat.addWidget(w.grid, 1)
    w.empty = QLabel('')
    w.empty.setObjectName('muted')
    w.empty.setAlignment(Qt.AlignCenter)
    w.empty.setWordWrap(True)
    w.empty.setStyleSheet('font-size:17px')
    w.empty.hide()
    cat.addWidget(w.empty, 1)
    w.stack.addWidget(catalog)

    detail = QWidget()
    detail_layout = QVBoxLayout(detail)
    detail_layout.setContentsMargins(0, 0, 0, 0)
    detail_layout.setSpacing(22)
    detail_layout.addWidget(action('Back to browsing', lambda: w.stack.setCurrentIndex(0), 'back', quiet=True), 0, Qt.AlignLeft)
    card = QFrame()
    card.setObjectName('detailCard')
    body = QHBoxLayout(card)
    body.setContentsMargins(26, 28, 30, 28)
    body.setSpacing(30)
    w.detail_cover = QLabel()
    w.detail_cover.setFixedSize(255, 382)
    w.detail_cover.setAlignment(Qt.AlignCenter)
    w.detail_cover.setScaledContents(True)
    body.addWidget(w.detail_cover, 0, Qt.AlignTop)
    info = QVBoxLayout()
    info.setSpacing(15)
    eyebrow = QLabel('MOVIEBOX · READY WHEN YOU ARE')
    eyebrow.setObjectName('eyebrow')
    info.addWidget(eyebrow)
    w.detail_title = QLabel()
    w.detail_title.setObjectName('detailTitle')
    w.detail_title.setTextFormat(Qt.PlainText)
    w.detail_title.setWordWrap(True)
    info.addWidget(w.detail_title)
    w.detail_meta = QLabel()
    w.detail_meta.setObjectName('muted')
    w.detail_meta.setWordWrap(True)
    info.addWidget(w.detail_meta)
    w.description = QLabel()
    w.description.setTextFormat(Qt.PlainText)
    w.description.setWordWrap(True)
    w.description.setAlignment(Qt.AlignTop)
    w.description.setStyleSheet('font-size:14px')
    info.addWidget(w.description)
    info.addStretch()
    episode_row = QHBoxLayout()
    w.season, w.episode = FluentComboBox(), FluentComboBox()
    w.season.setMinimumWidth(140)
    w.episode.setMinimumWidth(140)
    w.season.currentIndexChanged.connect(w.populate_episodes)
    w.episode.currentIndexChanged.connect(w.update_episode_selection)
    episode_row.addWidget(w.season)
    episode_row.addWidget(w.episode)
    episode_row.addStretch()
    info.addLayout(episode_row)
    actions = QHBoxLayout()
    w.watch = action('Watch now', w.watch_current, 'play', primary=True)
    w.trailer = action('Trailer', w.watch_trailer, 'movie')
    w.save = action('My list', w.toggle_saved, 'bookmark')
    w.save.setMinimumWidth(116)
    for item in (w.watch, w.trailer, w.save):
        item.setMinimumHeight(42)
        actions.addWidget(item)
    actions.addStretch()
    info.addLayout(actions)
    w.detail_notice = QLabel('')
    w.detail_notice.setWordWrap(True)
    w.detail_notice.setObjectName('muted')
    info.addWidget(w.detail_notice)
    body.addLayout(info, 1)
    detail_layout.addWidget(card)
    w.episode_panel = QWidget()
    episodes_layout = QVBoxLayout(w.episode_panel)
    episodes_layout.setContentsMargins(4, 6, 4, 0)
    episodes_layout.setSpacing(12)
    w.episode_heading = QLabel('Episodes')
    w.episode_heading.setObjectName('nowTitle')
    episodes_layout.addWidget(w.episode_heading)
    w.episode_cards = QListWidget()
    w.episode_cards.setObjectName('episodeCards')
    w.episode_cards.setViewMode(QListView.IconMode)
    w.episode_cards.setResizeMode(QListView.Adjust)
    w.episode_cards.setMovement(QListView.Static)
    w.episode_cards.setUniformItemSizes(True)
    w.episode_cards.setGridSize(QSize(122, 52))
    w.episode_cards.setSpacing(2)
    w.episode_cards.setVerticalScrollMode(QListView.ScrollPerPixel)
    w.episode_cards.setMinimumHeight(62)
    w.episode_cards.setMaximumHeight(320)
    w.episode_cards.itemClicked.connect(w.activate_episode)
    w.episode_cards.itemActivated.connect(w.activate_episode)
    episodes_layout.addWidget(w.episode_cards)
    w.episode_panel.hide()
    detail_layout.addWidget(w.episode_panel)
    detail_layout.addStretch()
    detail_scroll = QScrollArea()
    detail_scroll.setFrameShape(QFrame.NoFrame)
    detail_scroll.setWidgetResizable(True)
    detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    detail_scroll.setWidget(detail)
    w.stack.addWidget(detail_scroll)

    player_page = QWidget()
    w.player_page = player_page
    player_layout = QVBoxLayout(player_page)
    w.player_layout = player_layout
    player_layout.setContentsMargins(0, 0, 0, 0)
    player_layout.setSpacing(12)
    w.player_header = QWidget()
    w.player_header.setObjectName('playerHeader')
    w.player_header.setMouseTracking(True)
    player_head = QHBoxLayout(w.player_header)
    player_head.setContentsMargins(0, 0, 0, 0)
    player_head.addWidget(action('', w.leave_player, 'back', quiet=True))
    w.now_title = QLabel()
    w.now_title.setObjectName('nowTitle')
    w.now_title.setTextFormat(Qt.PlainText)
    w.now_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    player_head.addWidget(w.now_title, 1)
    player_head.addWidget(action('Fullscreen', w.toggle_fullscreen, 'fullscreen', quiet=True))
    player_layout.addWidget(w.player_header)
    w.video = video_type()
    w.video.setStyleSheet('background:black;border-radius:12px')
    subtitle_size = max(16, min(44, int(w.state.get('subtitle_size', 24))))
    w.video.caption.setStyleSheet(f'background:rgba(0,0,0,180);color:white;font-size:{subtitle_size}px;font-weight:600;padding:8px;border-radius:7px')
    player_layout.addWidget(w.video, 1)
    controls = QFrame()
    w.player_controls = controls
    controls.setMouseTracking(True)
    controls.setObjectName('controlBar')
    control_layout = QVBoxLayout(controls)
    control_layout.setContentsMargins(16, 13, 16, 13)
    control_layout.setSpacing(12)
    w.progress = SeekSlider(Qt.Horizontal)
    w.progress.setRange(0, 0)
    w.progress.setSingleStep(5000)
    w.progress.setPageStep(30000)
    w.progress.seekRequested.connect(w.seek_to)
    control_layout.addWidget(w.progress)
    transport = QHBoxLayout()
    w.pause = action('Pause', w.toggle_pause, 'pause')
    transport.addWidget(w.pause)
    transport.addWidget(action('−10s', lambda: w.seek_to(max(0, w.player.position() - 10000)), quiet=True))
    transport.addWidget(action('+10s', lambda: w.seek_to(w.player.position() + 10000), quiet=True))
    w.clock = QLabel('0:00:00 / 0:00:00')
    w.clock.setObjectName('muted')
    transport.addWidget(w.clock)
    transport.addStretch()
    w.next_episode = action('Next', w.play_next_episode, 'next', quiet=True)
    w.download_button = action('Download', w.download_current, 'download', quiet=True)
    transport.addWidget(w.next_episode)
    transport.addWidget(w.download_button)
    w.volume = QSlider(Qt.Horizontal)
    w.volume.setRange(0, 100)
    w.volume.setValue(70)
    w.volume.setFixedWidth(85)
    w.volume.setToolTip('Volume')
    transport.addWidget(w.volume)
    control_layout.addLayout(transport)
    options = QHBoxLayout()
    w.quality = FluentComboBox()
    w.quality.setMinimumWidth(184)
    w.quality.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    w.quality.setMinimumContentsLength(12)
    w.quality.view().setMinimumWidth(230)
    w.quality.setToolTip('Playback quality')
    w.quality.setAccessibleName('Playback quality')
    w.quality.currentIndexChanged.connect(w.change_quality)
    w.caption_selector = FluentComboBox()
    w.caption_selector.setMinimumWidth(145)
    w.caption_selector.addItem('Subtitles off', None)
    w.caption_selector.setToolTip('Subtitle language')
    w.caption_selector.setAccessibleName('Subtitle language')
    w.caption_selector.currentIndexChanged.connect(w.change_captions)
    options.addWidget(w.quality)
    options.addWidget(w.caption_selector)
    w.subtitle_tools = action('Subtitle tools', None, 'subtitle', quiet=True)
    w.subtitle_tools_menu = QMenu(w)
    w.subtitle_tools_menu.addAction('Import an SRT or WebVTT file…', w.open_subtitles)
    timing = QWidget()
    timing_layout = QHBoxLayout(timing)
    timing_layout.setContentsMargins(14, 10, 14, 10)
    timing_layout.addWidget(QLabel('Subtitle timing'))
    w.subtitle_delay = QSpinBox()
    w.subtitle_delay.setRange(-10000, 10000)
    w.subtitle_delay.setSingleStep(100)
    w.subtitle_delay.setSuffix(' ms')
    w.subtitle_delay.setToolTip('Subtitle timing · Positive values display later')
    w.subtitle_delay.setFixedWidth(95)
    timing_layout.addWidget(w.subtitle_delay)
    timing_action = QWidgetAction(w.subtitle_tools_menu)
    timing_action.setDefaultWidget(timing)
    w.subtitle_tools_menu.addAction(timing_action)
    w.subtitle_tools.clicked.connect(lambda: w.subtitle_tools_menu.exec(w.subtitle_tools.mapToGlobal(QPoint(0, w.subtitle_tools.height()))))
    options.addWidget(w.subtitle_tools)
    w.audio_tracks = FluentComboBox()
    w.audio_tracks.setMinimumWidth(200)
    w.audio_tracks.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    w.audio_tracks.setMinimumContentsLength(14)
    w.audio_tracks.addItem('Audio · Original', None)
    w.audio_tracks.setToolTip('Audio language')
    w.audio_tracks.setAccessibleName('Audio language')
    w.audio_tracks.currentIndexChanged.connect(w.change_audio)
    options.insertWidget(1, w.audio_tracks)
    QWidget.setTabOrder(w.quality, w.audio_tracks)
    QWidget.setTabOrder(w.audio_tracks, w.caption_selector)
    options.addStretch()
    w.autoplay = QCheckBox('Autoplay next')
    options.addWidget(w.autoplay)
    control_layout.addLayout(options)
    player_layout.addWidget(controls)
    w.stack.addWidget(player_page)

    downloads_page = QWidget()
    download_layout = QVBoxLayout(downloads_page)
    download_layout.setContentsMargins(0, 0, 0, 0)
    download_layout.setSpacing(15)
    heading = QLabel('Your downloads')
    heading.setObjectName('heading')
    download_layout.addWidget(heading)
    explanation = QLabel('Your favorites, ready for wherever life takes you. Double-click a finished video to play.')
    explanation.setObjectName('pageSubtitle')
    explanation.setWordWrap(True)
    download_layout.addWidget(explanation)
    w.download_list = QListWidget()
    w.download_list.itemActivated.connect(w.open_download)
    download_layout.addWidget(w.download_list, 1)
    w.download_empty = QFrame()
    empty_layout = QVBoxLayout(w.download_empty)
    empty_layout.setAlignment(Qt.AlignCenter)
    empty_icon = QLabel()
    empty_icon.setAlignment(Qt.AlignCenter)
    empty_icon.setPixmap(icon('download', ACCENT, 54).pixmap(54, 54))
    empty_layout.addWidget(empty_icon)
    empty_title = QLabel('Your offline library starts here')
    empty_title.setAlignment(Qt.AlignCenter)
    empty_title.setStyleSheet('font-size:20px;font-weight:600;margin-top:12px')
    empty_layout.addWidget(empty_title)
    empty_body = QLabel('Choose Download in the player to keep a video on this PC.')
    empty_body.setAlignment(Qt.AlignCenter)
    empty_body.setObjectName('muted')
    empty_layout.addWidget(empty_body)
    download_layout.addWidget(w.download_empty, 1)
    download_layout.addWidget(action('Pause active downloads', w.pause_downloads, 'pause'), 0, Qt.AlignLeft)
    w.stack.addWidget(downloads_page)
    w.shortcuts = []  # Application input routing also covers the cinema window.
    set_nav(w, 'home')
    def stack_changed(index):
        if index == 0:
            selected = next((name for name, button in w.nav_buttons.items() if button.isChecked()), '')
            set_nav(w, selected)
        else:
            w.breadcrumb.setText('MovieBox  /  ' + {1:'Details',2:'Now playing',3:'Downloads'}.get(index, 'Discover'))
    w.stack.currentChanged.connect(stack_changed)
    QTimer.singleShot(0, lambda: apply_window_material(w, bool(QApplication.instance().property('movieboxDark'))))
