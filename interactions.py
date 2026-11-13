"""Native input behavior and a borderless, mouse-revealed cinema surface."""
from PySide6.QtCore import Qt, QEvent, QObject, QTimer, Signal
from PySide6.QtGui import QCursor, QWindow
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSlider,
    QStyle, QStyleOptionSlider, QAbstractButton, QLineEdit, QComboBox,
    QAbstractSpinBox, QAbstractItemView, QListWidget, QListView, QStyledItemDelegate)


class ComboItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 36))
        return size

    def paint(self, painter, option, index):
        option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)


class FluentComboBox(QComboBox):
    """Readable popup rows; scrolling the page must not switch seasons."""
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setMouseTracking(True)
        view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setItemDelegate(ComboItemDelegate(view))
        self.setView(view)
        self.setMaxVisibleItems(10)
        self.setFocusPolicy(Qt.StrongFocus)

    def showPopup(self):
        self.view().setMinimumWidth(max(200, self.width()))
        super().showPopup()

    def wheelEvent(self, event):
        if self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


class SeekSlider(QSlider):
    seekRequested = Signal(int)

    def __init__(self, orientation=Qt.Horizontal):
        super().__init__(orientation)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.dragging = False

    def value_at(self, point):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        span = max(1, groove.width() - handle.width())
        position = max(0, min(span, round(point.x() - groove.x() - handle.width() / 2)))
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), position, span, option.upsideDown)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
            self.dragging = True
            self.setSliderDown(True)
            self.setValue(self.value_at(event.position()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.setValue(self.value_at(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.setValue(self.value_at(event.position()))
            self.dragging = False
            self.setSliderDown(False)
            self.seekRequested.emit(self.value())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        previous = self.value()
        super().keyPressEvent(event)
        if self.value() != previous:
            self.seekRequested.emit(self.value())


class CinemaWindow(QWidget):
    def __init__(self, window):
        super().__init__(window, Qt.Window | Qt.FramelessWindowHint)
        self.owner = window
        self.setWindowTitle('MovieBox')
        self.setStyleSheet('background:black')
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.layout_box.setSpacing(0)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_controls)
        self.mouse_timer = QTimer(self)
        self.mouse_timer.setInterval(50)
        self.mouse_timer.timeout.connect(self.check_cursor)
        self.controls_visible = False

    def enter(self):
        w = self.owner
        w.input_router.last_mouse = QCursor.pos()
        self.cursor_position = QCursor.pos()
        for widget in (w.player_header, w.video, w.player_controls):
            w.player_layout.removeWidget(widget)
        self.layout_box.addWidget(w.video, 1)
        w.video.caption.setParent(self, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        for panel in (w.player_header, w.player_controls):
            panel.setParent(self, Qt.Tool | Qt.FramelessWindowHint)
            panel.setAttribute(Qt.WA_ShowWithoutActivating, True)
        w.player_header.setObjectName('fullscreenHeader')
        w.player_header.setStyleSheet('background:rgba(12,17,24,220);border-radius:10px')
        w.video.setStyleSheet('background:black;border:0;border-radius:0')
        self.setScreen(w.screen())
        self.showFullScreen()
        w.video.show()
        w.position_changed(w.player.position())
        w.video.setFocus(Qt.OtherFocusReason)
        self.hide_controls(force=True)
        self.activateWindow()
        self.mouse_timer.start()

    def check_cursor(self):
        point = QCursor.pos()
        if point != self.cursor_position:
            self.cursor_position = point
            if self.frameGeometry().contains(point):
                self.reveal_controls()

    def leave(self):
        self.hide_timer.stop()
        self.mouse_timer.stop()
        w = self.owner
        self.hide()
        self.layout_box.removeWidget(w.video)
        for widget in (w.player_header, w.video, w.player_controls):
            widget.setParent(w.player_page)
        w.video.caption.setParent(w, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        w.player_header.setObjectName('playerHeader')
        w.player_header.setStyleSheet('background:transparent')
        w.video.setStyleSheet('background:black;border-radius:12px')
        w.player_layout.insertWidget(0, w.player_header)
        w.player_layout.insertWidget(1, w.video, 1)
        w.player_layout.insertWidget(2, w.player_controls)
        for widget in (w.player_header, w.video, w.player_controls):
            widget.show()
            widget.unsetCursor()
        self.unsetCursor()
        self.controls_visible = False
        w.video.position_caption()
        w.position_changed(w.player.position())
        w.activateWindow()
        w.video.setFocus(Qt.OtherFocusReason)

    def reveal_controls(self):
        if not self.isVisible():
            return
        self.controls_visible = True
        w = self.owner
        for widget in (w.player_header, w.player_controls):
            widget.show()
            widget.raise_()
        self.unsetCursor()
        w.video.unsetCursor()
        self.position_overlays()
        self.hide_timer.start(2200)

    def hide_controls(self, force=False):
        if not force and (QApplication.mouseButtons() or QApplication.activePopupWidget()):
            self.hide_timer.start(1000)
            return
        self.controls_visible = False
        self.owner.player_header.hide()
        self.owner.player_controls.hide()
        self.setCursor(Qt.BlankCursor)
        self.owner.video.setCursor(Qt.BlankCursor)
        self.owner.video.position_caption()

    def position_overlays(self):
        w = self.owner
        width, height = w.video.width(), w.video.height()
        origin = w.video.mapToGlobal(w.video.rect().topLeft())
        w.player_header.setGeometry(origin.x() + 20, origin.y() + 14, max(100, width - 40), 48)
        controls_height = max(138, w.player_controls.sizeHint().height())
        w.player_controls.setGeometry(origin.x() + 20, origin.y() + max(64, height - controls_height - 20), max(100, width - 40), controls_height)
        w.video.position_caption()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.position_overlays)

    def closeEvent(self, event):
        event.ignore()
        self.owner.toggle_fullscreen()


class InputRouter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.w = window
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        w = self.w
        stage = getattr(w, 'cinema', None)
        cinema = bool(stage and stage.isVisible())
        mouse_event = event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonDblClick)
        if mouse_event and hasattr(event, 'globalPosition'):
            point = event.globalPosition().toPoint()
            if cinema and stage.frameGeometry().contains(point):
                if event.type() != QEvent.MouseMove or getattr(self, 'last_mouse', None) != point:
                    self.last_mouse = point
                    stage.reveal_controls()
            if isinstance(obj, QWindow) and event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                video_point = w.video.mapFromGlobal(point)
                panels = (w.player_header, w.player_controls)
                over_panel = any(p.isVisible() and p.rect().contains(p.mapFromGlobal(point)) for p in panels)
                if w.stack.currentIndex() == 2 and w.video.rect().contains(video_point) and not over_panel:
                    w.toggle_fullscreen()
                    return True
        if isinstance(obj, QWidget):
            top = QWidget.window(obj)
            belongs = top is w or (cinema and top in (stage, w.player_header, w.player_controls))
        elif isinstance(obj, QWindow):
            belongs = QApplication.activeWindow() in (w, stage, w.player_header, w.player_controls)
        else:
            return False
        if not belongs:
            return False
        if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            inside_video = isinstance(obj, QWidget) and (obj is w.video or w.video.isAncestorOf(obj))
            inside_controls = isinstance(obj, QWidget) and any(obj is panel or panel.isAncestorOf(obj) for panel in (w.player_header, w.player_controls))
            if inside_video and not inside_controls:
                w.toggle_fullscreen()
                event.accept()
                return True
        if event.type() != QEvent.KeyPress:
            return False
        key = event.key()
        focus = QApplication.focusWidget()
        if key == Qt.Key_F11:
            w.toggle_fullscreen()
            return True
        if key == Qt.Key_Escape:
            popup = QApplication.activePopupWidget()
            if popup:
                popup.hide()
            else:
                w.escape()
            return True
        if key == Qt.Key_K and event.modifiers() & Qt.ControlModifier:
            if cinema:
                w.toggle_fullscreen()
            w.search.setFocus()
            w.search.selectAll()
            return True
        if cinema:
            stage.reveal_controls()
            if key in (Qt.Key_Tab, Qt.Key_Backtab):
                controls = []
                for panel in (w.player_header, w.player_controls):
                    controls.extend(child for child in panel.findChildren(QWidget)
                        if child.isVisible() and child.isEnabled() and child.focusPolicy() & Qt.TabFocus)
                if controls:
                    offset = -1 if key == Qt.Key_Backtab or event.modifiers() & Qt.ShiftModifier else 1
                    index = controls.index(focus) if focus in controls else (-1 if offset > 0 else 0)
                    controls[(index + offset) % len(controls)].setFocus(Qt.TabFocusReason)
                    return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if isinstance(focus, QAbstractButton) and focus.isEnabled():
                focus.click()
                return True
            if isinstance(focus, QComboBox):
                focus.showPopup()
                return True
            if isinstance(focus, QListWidget) and focus.currentItem():
                focus.itemActivated.emit(focus.currentItem())
                return True
            if focus is w.grid and w.grid.currentIndex().isValid():
                w.grid.activated.emit(w.grid.currentIndex())
                return True
        if isinstance(focus, QAbstractButton) and key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            if hasattr(w, 'theme_navigation') and w.theme_navigation.isAncestorOf(focus):
                choices = [b for b in w.theme_nav_buttons.values() if b.isVisible() and b.isEnabled()]
                if key in (Qt.Key_Left, Qt.Key_Right) and focus in choices:
                    choices[(choices.index(focus) + (1 if key == Qt.Key_Right else -1)) % len(choices)].setFocus()
                elif key == Qt.Key_Down:
                    w.search.setFocus()
                return True
            if w.sidebar.isAncestorOf(focus):
                choices = [b for b in w.sidebar.findChildren(QAbstractButton) if b.isVisible() and b.isEnabled()]
                if focus in choices:
                    offset = 1 if key in (Qt.Key_Right, Qt.Key_Down) else -1
                    choices[(choices.index(focus) + offset) % len(choices)].setFocus()
                    return True
            QWidget.window(focus).focusNextPrevChild(key in (Qt.Key_Right, Qt.Key_Down))
            return True
        typing = isinstance(focus, (QLineEdit, QAbstractSpinBox, QComboBox))
        if w.stack.currentIndex() == 2 and not typing and not isinstance(focus, QAbstractButton):
            if key == Qt.Key_Space:
                w.toggle_pause()
                return True
            if key in (Qt.Key_Left, Qt.Key_Right) and not isinstance(focus, QSlider):
                w.seek_to(w.player.position() + (10000 if key == Qt.Key_Right else -10000))
                return True
        return False
