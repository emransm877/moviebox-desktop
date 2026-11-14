"""Fluent-inspired native Windows shell. All browsing and playback stay native Qt."""
from __future__ import annotations
import ctypes
from pathlib import Path
import sys
import winreg
from PySide6.QtCore import Qt, QSize, QRectF, QUrl, QTimer, QBuffer, QByteArray, QIODevice, QPoint
from PySide6.QtGui import (QColor, QPainter, QPixmap, QFont, QFontMetrics, QIcon, QLinearGradient,
    QPainterPath, QImageReader, QShortcut, QKeySequence)
from PySide6.QtWidgets import (QApplication, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QListView, QListWidget, QSlider,
    QSpinBox, QCheckBox, QStackedWidget, QSizePolicy, QDialog, QFileDialog, QScrollArea, QMenu, QWidgetAction)
from PySide6.QtSvg import QSvgRenderer
from interactions import SeekSlider, FluentComboBox
from themes import THEMES, palette, initial_theme, theme_key


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
    if name.startswith('player-'):
        file=ASSETS/'player-icons'/(name[7:]+'.svg')
        if file.is_file():
            svg=file.read_text(encoding='utf-8').replace('#f2f6fa',color or '#f2f6fa')
            renderer=QSvgRenderer(svg.encode());pixmap=QPixmap(size*2,size*2);pixmap.fill(Qt.transparent)
            painter=QPainter(pixmap);renderer.render(painter);painter.end();pixmap.setDevicePixelRatio(2)
            return QIcon(pixmap)
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


def refresh_theme(window, selection):
    p = palette(selection)
    QApplication.instance().setStyleSheet(stylesheet(selection))
    for widget in window.findChildren(QPushButton):
        glyph = widget.property('fluentGlyph')
        if glyph:
            widget.setIcon(icon(glyph, p['ink'] if widget.property('fluentPrimary') else None))
    window.search_action.setIcon(icon('search'))
    apply_window_material(window, p['dark'])
    if hasattr(window, 'theme_navigation'):
        apply_theme_layout(window)
    if hasattr(window, 'hero'):
        window.hero.apply_theme()
    themed_logo = ASSETS / ('moviebox-logo-' + QApplication.instance().property('movieboxTheme') + '.svg')
    window.setWindowIcon(QIcon(str(themed_logo)))
    if hasattr(window, 'brand_logo'):
        window.brand_logo.setPixmap(QIcon(str(themed_logo)).pixmap(40,44))
    window.grid.viewport().update()


def stylesheet(selection=True):
    global ACCENT
    p = palette(selection)
    dark = p['dark']
    ACCENT = p['accent']
    app = QApplication.instance()
    app.setProperty('movieboxDark', dark)
    app.setProperty('movieboxTheme', next(key for key, value in THEMES.items() if value is p))
    app.setProperty('movieboxAccent', p['accent'])
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
    QSpinBox{background:FIELD;border:1px solid LINE;border-radius:8px;padding:9px 30px 9px 14px;min-width:76px}
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
    QMenu#playerOptionsMenu::item{padding:8px 14px}
    QMenu#playerOptionsMenu::separator{height:1px;margin:4px 8px}
    QFrame#detailCard,QFrame#controlBar,QFrame#playerEpisodePanel{background:SURFACE;border:1px solid LINE;border-radius:16px}
    QListWidget#playerEpisodes::item{padding:10px;margin:3px}
    QListWidget#playerEpisodes::item:selected{background:SELECT;color:TEXT}
    QListWidget#episodeCards::item{padding:8px;margin:3px;background:SURFACE;border:1px solid LINE;border-radius:8px}
    QListWidget#episodeCards::item:selected{background:SELECT;border-color:#48e6b0;color:TEXT}
    '''
    for before, after in {'#48e6b0':p['accent'], '#08251a':p['ink'], '#65efc0':p['accent'], '#78f0c6':p['accent'], '#2fcb96':p['accent'], '#2c9c7b':p['select']}.items():
        css = css.replace(before, after)
    for name in ('base','panel','surface','hover','text','secondary','line','field','select'):
        value = p[name]
        css = css.replace(name.upper(), value)
    if p is THEMES['eclipse']:
        css += 'QLabel#heading,QLabel#brandName,QLabel#detailTitle{font-family:"Georgia"} '
    if p is THEMES['prism']:
        css += 'QFrame#contentPanel{border-color:#674887} '
    css += 'QFrame#themeNavigation{background:' + p['panel'] + ';border-radius:14px} '
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
        super().__init__(text)
        self.setObjectName('navItem')
        self.setIcon(icon(glyph))
        self.setProperty('fluentGlyph', glyph)
        self.setIconSize(QSize(19, 19))
        self.setCheckable(selectable)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(45)
        bold = QFont(self.font());bold.setPixelSize(14);bold.setWeight(QFont.DemiBold)
        self.label_width = QFontMetrics(bold).horizontalAdvance(text) + 64
        self.setMinimumWidth(self.label_width)
        self.clicked.connect(callback)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(QRectF(0, self.height() / 2 - 10, 3, 20), 1.5, 1.5)


def action(text, callback=None, glyph=None, *, primary=False, quiet=False, icon_only=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.PointingHandCursor)
    if glyph:
        widget.setIcon(icon(glyph, palette(QApplication.instance().property('movieboxTheme'))['ink'] if primary else None))
        widget.setProperty('fluentGlyph', glyph)
        widget.setProperty('fluentPrimary', primary)
        widget.setIconSize(QSize(18, 18))
    if primary:
        widget.setObjectName('primary')
    elif quiet:
        widget.setObjectName('quiet')
    if icon_only:
        widget.setToolTip(text)
        widget.setAccessibleName(text)
        widget.setText('')
        widget.setFixedSize(42,40)
        widget.setIconSize(QSize(22,22))
        widget.setStyleSheet('padding:8px')
    if callback:
        widget.clicked.connect(callback)
    return widget


class PlayerIconPicker(FluentComboBox):
    """Keep the real accessible selector and popup, painting only its player icon."""
    def __init__(self,glyph,label):
        super().__init__();self.glyph=glyph;self.label=label
        self.setFixedSize(42,40);self.setAccessibleName(label)
        self.currentIndexChanged.connect(self.update_label);self.update_label()

    def update_label(self,*_):
        self.setToolTip(self.label+(': '+self.currentText() if self.currentText() else ''));self.update()

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        if self.underMouse() or self.hasFocus():
            painter.setPen(QColor(palette(QApplication.instance().property('movieboxTheme'))['accent']) if self.hasFocus() else Qt.NoPen)
            painter.setBrush(QColor(255,255,255,28));painter.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),8,8)
        icon('player-'+self.glyph,'#f2f6fa' if self.isEnabled() else '#68717b',24).paint(painter,(self.width()-24)//2,(self.height()-24)//2,24,24)


class AspectImageLabel(QLabel):
    """Retain the original decoded image and fit it without stretching or clipping."""
    def __init__(self):
        super().__init__()
        self.original = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)

    def setPixmap(self, image):
        self.original = QPixmap(image)
        self.fit_image()

    def clear(self):
        self.original = QPixmap()
        super().clear()

    def fit_image(self):
        if not self.original.isNull():
            super().setPixmap(self.original.scaled(self.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fit_image()


class HeroCard(QWidget):
    def __init__(self, window, fetch_bytes):
        super().__init__()
        self.window, self.fetch_bytes = window, fetch_bytes
        self.image = QPixmap()
        self.loading_logo = QIcon(str(ASSETS / 'moviebox-logo.svg')).pixmap(128, 144)
        self.subject = None
        self.slides = []
        self.slide_index = 0
        self.rotation_paused = False
        self.timer = QTimer(self)
        self.timer.setInterval(8000)
        self.timer.timeout.connect(lambda: self.advance(1, automatic=True))
        self.timer.start()
        self.generation = 0
        self.setMinimumHeight(248)
        self.setMaximumHeight(270)
        content = QVBoxLayout(self)
        content.setContentsMargins(28, 23, 28, 23)
        content.setSpacing(9)
        eyebrow = QLabel('LATEST MOVIES + TV SHOWS')
        self.eyebrow = eyebrow
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
        actions.setSpacing(8)
        self.explore = action('Watch now', self.open, 'play', primary=True)
        self.explore.setFixedWidth(145)
        actions.addWidget(self.explore)
        self.info = action('More info', self.more_info)
        actions.addWidget(self.info)
        self.save = action('My list', self.save_subject, 'bookmark')
        self.save.setStyleSheet('QPushButton{background:rgba(255,255,255,20);color:white;border:1px solid rgba(255,255,255,50)}QPushButton:hover{background:rgba(255,255,255,38)}')
        actions.addWidget(self.save)
        actions.addStretch()
        self.previous = action('‹', lambda: self.advance(-1))
        self.previous.setAccessibleName('Previous spotlight title')
        self.next = action('›', lambda: self.advance(1))
        self.next.setAccessibleName('Next spotlight title')
        self.pause_rotation = action('Ⅱ', self.toggle_rotation)
        self.pause_rotation.setAccessibleName('Pause slideshow')
        self.counter = QLabel('1 / 1')
        for control in (self.previous, self.next, self.pause_rotation):
            control.setFixedWidth(34)
            control.setStyleSheet('padding:8px 2px')
            actions.addWidget(control)
        actions.addWidget(self.counter)
        content.addLayout(actions)
        self.apply_theme()

    def apply_theme(self):
        p = palette(QApplication.instance().property('movieboxTheme'))
        family = 'Georgia' if p is THEMES['eclipse'] else 'Segoe UI Variable Display'
        self.title.setStyleSheet(f'color:{p["text"]};font-family:"{family}";font-size:{24 if getattr(self,"compact",False) else 31}px;font-weight:650;background:transparent')
        self.meta.setStyleSheet(f'color:{p["secondary"]};font-size:12px')
        self.eyebrow.setStyleSheet(f'color:{p["accent"]};font-size:10px;font-weight:650;letter-spacing:2px')
        self.save.setStyleSheet('')
        self.loading_logo = QIcon(str(ASSETS / ('moviebox-logo-' + QApplication.instance().property('movieboxTheme') + '.svg'))).pixmap(128,144)
        self.update()

    def set_slides(self, subjects):
        seen = set()
        slides = []
        for subject in subjects:
            identity = str(subject.get('subjectId') or '')
            if identity and identity not in seen:
                slides.append(subject); seen.add(identity)
        if not slides:
            return
        # Preserve the exact active title while the latest-feed request completes.
        active = str((self.subject or {}).get('subjectId') or '')
        self.slides = slides[:100]
        self.slide_index = next((i for i, subject in enumerate(self.slides) if str(subject['subjectId']) == active), 0)
        if QApplication.focusWidget() and self.isAncestorOf(QApplication.focusWidget()):
            # Never change a focused Watch/More info target under the user.
            if active and not any(str(s['subjectId']) == active for s in self.slides):
                self.slides = [self.subject] + self.slides[:99]
                self.slide_index = 0
        self.set_subject(self.slides[self.slide_index])
        self.counter.setText(f'{self.slide_index + 1} / {len(self.slides)}')

    def advance(self, step, automatic=False):
        focused = QApplication.focusWidget()
        if automatic and (self.rotation_paused or not self.isVisible() or not self.window.isActiveWindow()
                          or self.underMouse() or (focused and self.isAncestorOf(focused))
                          or self.window.stack.currentIndex() != 0 or not self.window.poster_delegate.motion):
            return
        if len(self.slides) < 2:
            return
        self.slide_index = (self.slide_index + step) % len(self.slides)
        self.set_subject(self.slides[self.slide_index])
        self.counter.setText(f'{self.slide_index + 1} / {len(self.slides)}')
        self.timer.start()

    def toggle_rotation(self):
        self.rotation_paused = not self.rotation_paused
        self.pause_rotation.setText('▶' if self.rotation_paused else 'Ⅱ')
        self.pause_rotation.setAccessibleName('Resume slideshow' if self.rotation_paused else 'Pause slideshow')

    def more_info(self):
        if self.subject:
            self.window.hero_auto_play = ''
            self.window.open_detail(self.subject)

    def set_compact(self, compact):
        if getattr(self, 'compact', None) == compact:
            return
        self.compact = compact
        self.setFixedHeight(172 if compact else 248)
        self.layout().setContentsMargins(24, 15, 24, 15) if compact else self.layout().setContentsMargins(28, 23, 28, 23)
        self.layout().setSpacing(6 if compact else 9)
        self.layout().itemAt(0).widget().setVisible(not compact)
        self.apply_theme()

    def set_subject(self, subject):
        if self.subject and self.subject.get('subjectId') == subject.get('subjectId'):
            return
        self.subject = subject
        self.image = QPixmap()
        self.update()
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
        p = palette(QApplication.instance().property('movieboxTheme'))
        painter.fillRect(self.rect(), QColor(p['hero']))
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
        for stop, alpha in ((0,252),(.45,226),(.78,65),(1,12)):
            shade = QColor(p['hero']); shade.setAlpha(alpha)
            gradient.setColorAt(stop, shade)
        painter.fillRect(self.rect(), gradient)
        vertical = QLinearGradient(0, 0, 0, self.height())
        vertical.setColorAt(0, QColor(0, 0, 0, 0))
        vertical.setColorAt(1, QColor(0, 7, 12, 90 if p['dark'] else 8))
        painter.fillRect(self.rect(), vertical)
        painter.setClipping(False)
        painter.setPen(QColor(255, 255, 255, 22))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 18, 18)


def set_nav(window, name):
    for key, widget in window.nav_buttons.items():
        widget.setChecked(key == name)
    for key, widget in getattr(window, 'theme_nav_buttons', {}).items():
        widget.setChecked(key == name)
    if hasattr(window, 'breadcrumb'):
        label = {'home':'Discover','movies':'Movies','series':'TV Shows','anime':'Anime',
                 'saved':'My list','history':'Continue watching','downloads':'Downloads'}.get(name, 'Search')
        window.breadcrumb.setText('MovieBox  /  ' + label)


def browse_kind(window, name):
    if name in ('movies', 'series'):
        window.browse_catalogue(name)
        return
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


def apply_theme_layout(window):
    p = palette(QApplication.instance().property('movieboxTheme'))
    rail = p['layout'] != 'sidebar'
    window.sidebar.setFixedWidth(76 if rail else 212)
    window.theme_navigation.setVisible(p['layout'] == 'top')
    for label in window.sidebar.findChildren(QLabel):
        label.setVisible(not rail or label.objectName() == 'brandLogo')
    for button in window.sidebar.findChildren(NavButton):
        if not hasattr(button, 'full_label'):
            button.full_label = button.text()
        button.setToolTip(button.full_label.strip())
        button.setAccessibleName(button.full_label.strip())
        button.setText('' if rail else button.full_label)
        button.setMinimumWidth(0 if rail else min(button.label_width,194))
    window.grid.doItemsLayout()


def open_settings(window):
    dialog = QDialog(window)
    dialog.setWindowTitle('MovieBox settings')
    dialog.setMinimumWidth(470)
    available = QApplication.primaryScreen().availableGeometry()
    dialog.resize(560, min(760, available.height() - 80))
    dialog.setMaximumHeight(max(450, available.height() - 60))
    outer = QVBoxLayout(dialog)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    body = QWidget()
    scroll.setWidget(body)
    outer.addWidget(scroll)
    layout = QVBoxLayout(body)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(18)
    title = QLabel('Make it yours')
    title.setObjectName('heading')
    layout.addWidget(title)
    layout.addWidget(QLabel('MovieBox theme'))
    appearance = FluentComboBox()
    appearance.setObjectName('themePicker')
    appearance.setAccessibleName('MovieBox theme')
    modes = list(THEMES)
    for key in modes:
        appearance.addItem(THEMES[key]['name'], key)
    appearance.setCurrentIndex(modes.index(initial_theme(window.state, system_is_dark())))
    theme_hint = QLabel(THEMES[modes[appearance.currentIndex()]]['description'])
    theme_hint.setWordWrap(True)
    theme_hint.setObjectName('muted')
    def change(index):
        mode = modes[index]
        window.state['theme'] = mode
        window.state['appearance'] = 'theme'
        appearance_mode.blockSignals(True)
        appearance_mode.setCurrentIndex(0)
        appearance_mode.blockSignals(False)
        window.persist()
        refresh_theme(window, mode)
        theme_hint.setText(THEMES[mode]['description'])
        apply_window_material(dialog, THEMES[mode]['dark'])
    appearance.currentIndexChanged.connect(change)
    layout.addWidget(appearance)
    layout.addWidget(theme_hint)
    # Preserve the previous Dark / Light / Follow Windows appearance feature.
    layout.addWidget(QLabel('Appearance'))
    appearance_mode = FluentComboBox()
    appearance_mode.setObjectName('appearancePicker')
    appearance_modes = ['theme','dark','light','system']
    appearance_mode.addItems(['Use selected theme colours','Dark','Light','Follow Windows'])
    appearance_mode.setCurrentIndex(appearance_modes.index(window.state.get('appearance','theme')) if window.state.get('appearance','theme') in appearance_modes else 0)
    def change_appearance(index):
        mode = appearance_modes[index]
        window.state['appearance'] = mode
        if mode != 'theme':
            key = 'aurora' if mode == 'light' or (mode == 'system' and not system_is_dark()) else 'obsidian'
            window.state['theme'] = key
            appearance.blockSignals(True)
            appearance.setCurrentIndex(modes.index(key))
            appearance.blockSignals(False)
            theme_hint.setText(THEMES[key]['description'])
        refresh_theme(window, window.state.get('theme','obsidian'))
        window.persist()
    appearance_mode.currentIndexChanged.connect(change_appearance)
    layout.addWidget(appearance_mode)
    layout.addWidget(QLabel('Subtitle text size'))
    size = QSpinBox()
    size.setObjectName('subtitleSize')
    size.setRange(16, 44)
    size.setSuffix(' px')
    size.setValue(int(window.state.get('subtitle_size', 24)))
    size.lineEdit().setTextMargins(14,0,10,0)
    size.lineEdit().setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
    outer.addWidget(action('Done', dialog.accept, primary=True), 0, Qt.AlignRight)
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
    brand.setObjectName('brandLogo')
    w.brand_logo = brand
    brand.setPixmap(QIcon(str(ASSETS / 'moviebox-logo.svg')).pixmap(32, 36))
    brand.setFixedSize(40, 44)
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
               ('series','TV Shows','series',lambda: browse_kind(w,'series')),
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
    w.theme_navigation = QFrame()
    w.theme_navigation.setObjectName('themeNavigation')
    theme_nav = QHBoxLayout(w.theme_navigation)
    theme_nav.setContentsMargins(12, 2, 12, 2)
    w.theme_nav_buttons = {}
    for key, text, glyph, callback in entries[:3] + [('saved','My list','bookmark',w.show_saved)]:
        item = NavButton(text, glyph, callback)
        w.theme_nav_buttons[key] = item
        theme_nav.addWidget(item)
    theme_nav.addStretch()
    column.addWidget(w.theme_navigation)
    w.theme_navigation.hide()
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
    w.history_toolbar = QWidget()
    history_tools = QHBoxLayout(w.history_toolbar)
    history_tools.setContentsMargins(0,0,0,0)
    w.history_select = action('Select titles', w.begin_history_selection)
    w.history_all = action('Select all', w.select_all_history)
    w.history_remove = action('Remove selected', w.remove_selected_history)
    w.history_done = action('Done selecting', w.finish_history_selection)
    w.history_undo_button = action('Undo removal', w.undo_history_removal)
    for button in (w.history_select,w.history_all,w.history_remove,w.history_done,w.history_undo_button):
        history_tools.addWidget(button)
    history_tools.addStretch()
    w.history_toolbar.hide()
    cat.addWidget(w.history_toolbar)
    w.catalogue_filter_panel = QWidget()
    filter_layout = QVBoxLayout(w.catalogue_filter_panel)
    filter_layout.setContentsMargins(0, 0, 0, 0)
    filter_layout.setSpacing(10)
    w.catalogue_filter_fields = {}
    filter_row=QHBoxLayout();filter_row.setSpacing(10)
    for field,label in (('genre','Genre'),('year','Year'),('country','Country'),('classify','Audio / edition'),('sort','Sort by'),('rate','Minimum rating')):
        block=QVBoxLayout();block.setSpacing(4)
        caption=QLabel(label);caption.setObjectName('muted');caption.setMinimumHeight(18);block.addWidget(caption)
        picker=FluentComboBox();picker.setAccessibleName(label);picker.setToolTip('Filter catalogue by '+label.lower())
        minimum=max(84,caption.fontMetrics().horizontalAdvance(label)+12);picker.setProperty('catalogueMinimumWidth',minimum)
        def fit_filter(*_,control=picker,minimum=minimum):control.setFixedWidth(max(minimum,control.fontMetrics().horizontalAdvance(control.currentText())+56))
        picker.currentIndexChanged.connect(fit_filter);picker.addItem('Loading…','');fit_filter()
        block.addWidget(picker);w.catalogue_filter_fields[field]=picker;filter_row.addLayout(block)
    filter_row.addStretch();filter_layout.addLayout(filter_row)
    filter_actions = QHBoxLayout()
    filter_actions.addStretch()
    w.catalogue_apply = action('Apply filters', w.apply_catalogue_filters, primary=True)
    w.catalogue_apply.setMinimumWidth(132)
    w.catalogue_reset = action('Reset', w.reset_catalogue_filters)
    w.catalogue_reset.setMinimumWidth(84)
    filter_actions.addWidget(w.catalogue_apply)
    filter_actions.addWidget(w.catalogue_reset)
    filter_layout.addLayout(filter_actions)
    w.catalogue_filter_panel.hide()
    cat.addWidget(w.catalogue_filter_panel)
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
    w.grid.clicked.connect(w.catalogue_clicked)
    w.grid.activated.connect(w.catalogue_activated)
    w.grid.selectionModel().selectionChanged.connect(w.update_history_selection)
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
    w.detail_cover = AspectImageLabel()
    w.detail_cover.setFixedSize(255, 382)
    w.detail_cover.setAlignment(Qt.AlignCenter)
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
    w.season_row = QWidget()
    episode_row = QHBoxLayout(w.season_row)
    episode_row.setContentsMargins(0,0,0,0)
    w.season, w.episode = FluentComboBox(), FluentComboBox()
    w.season.setMinimumWidth(140)
    w.episode.setMinimumWidth(140)
    w.season.currentIndexChanged.connect(w.populate_episodes)
    w.episode.currentIndexChanged.connect(w.update_episode_selection)
    episode_row.addWidget(w.season)
    episode_row.addWidget(w.episode)
    episode_row.addStretch()
    info.addWidget(w.season_row)
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
    info.addStretch()
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
    w.player_transport_layout=transport
    transport.setSpacing(5)
    w.pause = action('Pause',w.toggle_pause,'player-pause',quiet=True,icon_only=True)
    transport.addWidget(w.pause)
    transport.addWidget(action('Seek back 10 seconds',lambda:w.seek_to(max(0,w.player.position()-10000)),'player-skip-back',quiet=True,icon_only=True))
    transport.addWidget(action('Seek forward 10 seconds',lambda:w.seek_to(w.player.position()+10000),'player-skip-forward',quiet=True,icon_only=True))
    w.mute_button=action('Volume',None,'player-volume-high',quiet=True,icon_only=True)
    transport.addWidget(w.mute_button)
    w.volume_menu=QMenu(w);w.volume_menu.setObjectName('playerVolumeMenu')
    w.volume_menu.setStyleSheet('QMenu#playerVolumeMenu{background:#151e28;border:1px solid #344454;padding:0} QMenu#playerVolumeMenu QLabel{color:#f2f6fa} QMenu#playerVolumeMenu QPushButton{background:transparent;color:#f2f6fa;border:1px solid transparent} QMenu#playerVolumeMenu QPushButton:hover{background:#283543}')
    w.mute_button.setAccessibleDescription('Open volume controls')
    volume_panel=QWidget();volume_layout=QVBoxLayout(volume_panel);volume_layout.setContentsMargins(14,12,14,12);volume_layout.setSpacing(10)
    volume_header=QHBoxLayout();volume_header.addWidget(QLabel('Volume'));volume_header.addStretch()
    w.volume_level=QLabel('70%');volume_header.addWidget(w.volume_level);volume_layout.addLayout(volume_header)
    volume_row=QHBoxLayout();volume_row.setSpacing(10)
    w.volume_mute_toggle=action('Mute',lambda:w.audio.setMuted(not w.audio.isMuted()),'player-volume-high',quiet=True,icon_only=True)
    volume_row.addWidget(w.volume_mute_toggle)
    w.volume=QSlider(Qt.Horizontal);w.volume.setRange(0,100);w.volume.setValue(70);w.volume.setFixedWidth(170)
    w.volume.setToolTip('Volume');w.volume.setAccessibleName('Volume');volume_row.addWidget(w.volume);volume_layout.addLayout(volume_row)
    volume_action=QWidgetAction(w.volume_menu);volume_action.setDefaultWidget(volume_panel);w.volume_menu.addAction(volume_action)
    def show_volume():
        w.volume_menu.adjustSize();point=w.mute_button.mapToGlobal(QPoint(0,-w.volume_menu.sizeHint().height()-8))
        screen=w.mute_button.screen().availableGeometry();point.setX(max(screen.left()+6,min(point.x(),screen.right()-w.volume_menu.sizeHint().width()-6)))
        w.volume_menu.popup(point);w.volume.setFocus(Qt.PopupFocusReason)
    w.mute_button.clicked.connect(show_volume)
    w.clock=QLabel('0:00:00 / 0:00:00');w.clock.setObjectName('muted');transport.addWidget(w.clock)
    transport.addStretch()
    w.quality=PlayerIconPicker('settings-outline','Playback quality')
    w.quality.currentIndexChanged.connect(w.change_quality);transport.addWidget(w.quality)
    w.caption_selector=PlayerIconPicker('subtitles','Subtitle language');w.caption_selector.addItem('Subtitles off',None)
    w.caption_selector.currentIndexChanged.connect(w.change_captions);transport.addWidget(w.caption_selector)
    w.audio_tracks=PlayerIconPicker('audio-tracks','Audio language');w.audio_tracks.addItem('Audio · Original',None)
    w.audio_tracks.currentIndexChanged.connect(w.change_audio);transport.addWidget(w.audio_tracks)
    w.episode_browser_button=action('Seasons & episodes · Up arrow',w.open_player_episodes,'player-episodes',quiet=True,icon_only=True)
    w.episode_browser_button.hide();transport.addWidget(w.episode_browser_button)
    w.video_fit_button=action('Video size: Fit',w.cycle_video_fit,'player-video-scale-fit',quiet=True,icon_only=True)
    transport.addWidget(w.video_fit_button)
    w.fullscreen_button=action('Fullscreen · F11',w.toggle_fullscreen,'player-maximize',quiet=True,icon_only=True)
    transport.addWidget(w.fullscreen_button)
    w.subtitle_tools=action('More player options',None,'player-more-horizontal',quiet=True,icon_only=True)
    w.subtitle_tools_menu=QMenu(w)
    w.subtitle_tools_menu.setObjectName('playerOptionsMenu')
    w.download_button=action('Download',w.download_current,'download',quiet=True)
    w.download_button.setParent(controls);w.download_button.hide()
    w.player_download_action=w.subtitle_tools_menu.addAction('Download video',w.download_current)
    w.subtitle_tools_menu.aboutToShow.connect(lambda:w.player_download_action.setEnabled(w.download_button.isEnabled()))
    w.subtitle_tools_menu.addSeparator()
    w.subtitle_tools_menu.addAction('Import subtitles…',w.open_subtitles)
    timing=QWidget();timing_layout=QHBoxLayout(timing);timing_layout.setContentsMargins(14,8,14,8);timing_layout.setSpacing(12)
    timing_layout.addWidget(QLabel('Subtitle timing'))
    w.subtitle_delay=QSpinBox();w.subtitle_delay.setRange(-10000,10000);w.subtitle_delay.setSingleStep(100)
    w.subtitle_delay.setSuffix(' ms');w.subtitle_delay.setToolTip('Subtitle timing · Positive values display later');w.subtitle_delay.setFixedWidth(110)
    w.subtitle_delay.setFixedHeight(36)
    w.subtitle_delay.lineEdit().setTextMargins(10,0,6,0)
    w.subtitle_delay.lineEdit().setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
    timing_layout.addWidget(w.subtitle_delay)
    timing_action=QWidgetAction(w.subtitle_tools_menu);timing_action.setDefaultWidget(timing);w.subtitle_tools_menu.addAction(timing_action)
    def show_more():
        menu=w.subtitle_tools_menu;menu.adjustSize();point=w.subtitle_tools.mapToGlobal(QPoint(w.subtitle_tools.width()-menu.sizeHint().width(),-menu.sizeHint().height()-8));menu.popup(point)
    w.subtitle_tools.clicked.connect(show_more);transport.addWidget(w.subtitle_tools)
    control_layout.addLayout(transport)
    controls.setStyleSheet('QFrame#controlBar{background:rgba(8,10,14,225);border:0;border-radius:0} QFrame#controlBar QPushButton{color:#f2f6fa;background:transparent;border:1px solid transparent} QFrame#controlBar QPushButton:hover{background:rgba(255,255,255,24)} QFrame#controlBar QPushButton:focus{border-color:#9caebf} QFrame#controlBar QLabel{color:#dce3eb}')
    control_layout.setContentsMargins(14,6,14,6);control_layout.setSpacing(4)
    QWidget.setTabOrder(w.quality,w.caption_selector);QWidget.setTabOrder(w.caption_selector,w.audio_tracks)
    player_layout.addWidget(controls)
    w.stack.addWidget(player_page)
    w.next_up_panel = QFrame(w,Qt.Tool | Qt.FramelessWindowHint)
    w.next_up_panel.setAttribute(Qt.WA_ShowWithoutActivating,True)
    w.next_up_panel.setObjectName('nextUpPanel')
    w.next_up_panel.setStyleSheet('QFrame#nextUpPanel{background:#151e28;border:1px solid #344454;border-radius:14px}QLabel{color:#f2f6fa}')
    next_layout=QVBoxLayout(w.next_up_panel)
    next_layout.setContentsMargins(20,16,20,16)
    w.next_up_label=QLabel('Up next')
    next_layout.addWidget(w.next_up_label)
    next_actions=QHBoxLayout()
    next_actions.addWidget(action('Play next',w.play_next_episode,'next',primary=True))
    next_actions.addWidget(action('Hide',w.dismiss_next_up))
    next_layout.addLayout(next_actions)
    w.next_up_panel.hide()

    w.player_episode_panel=QFrame(w,Qt.Tool|Qt.FramelessWindowHint)
    w.player_episode_panel.setObjectName('playerEpisodePanel')
    w.player_episode_panel.setCursor(Qt.ArrowCursor)
    drawer=QVBoxLayout(w.player_episode_panel)
    drawer.setContentsMargins(22,20,22,20);drawer.setSpacing(16)
    drawer_header=QHBoxLayout()
    drawer_title=QLabel('Seasons & episodes');drawer_title.setStyleSheet('font-size:20px;font-weight:600')
    drawer_header.addWidget(drawer_title);drawer_header.addStretch()
    drawer_header.addWidget(action('Close',w.close_player_episodes))
    drawer.addLayout(drawer_header)
    w.player_season_picker=FluentComboBox()
    w.player_season_picker.setFixedWidth(144)
    w.player_season_picker.setAccessibleName('Player season')
    w.player_season_picker.currentIndexChanged.connect(w.populate_player_episodes)
    drawer.addWidget(w.player_season_picker,0,Qt.AlignLeft)
    w.player_episode_list=QListWidget()
    w.player_episode_list.setObjectName('playerEpisodes')
    w.player_episode_list.setAccessibleName('Player episodes')
    w.player_episode_list.itemClicked.connect(w.play_player_episode)
    w.player_episode_list.itemActivated.connect(w.play_player_episode)
    drawer.addWidget(w.player_episode_list,1)
    drawer_hint=QLabel('Choose an episode to play. Browsing keeps your video playing.')
    drawer_hint.setWordWrap(True);drawer_hint.setObjectName('muted')
    drawer.addWidget(drawer_hint)
    w.player_episode_panel.hide()

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
    apply_theme_layout(w)
    refresh_theme(w, initial_theme(w.state,system_is_dark()))
