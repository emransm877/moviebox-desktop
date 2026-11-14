"""Native input behavior and a borderless, mouse-revealed cinema surface."""
from PySide6.QtCore import Qt, QEvent, QObject, QTimer, Signal, QPropertyAnimation, QEasingCurve, QPoint, QRectF
from PySide6.QtGui import QCursor, QWindow, QColor, QPainter
from themes import palette
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSlider, QStyleOptionComboBox,
    QStyle, QStyleOptionSlider, QAbstractButton, QLineEdit, QComboBox,
    QAbstractSpinBox, QAbstractItemView, QListWidget, QListView, QStyledItemDelegate)


class ComboItemDelegate(QStyledItemDelegate):
    def __init__(self,view,combo):
        super().__init__(view);self.combo=combo
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 36))
        return size

    def paint(self, painter, option, index):
        p=palette(QApplication.instance().property('movieboxTheme'))
        enabled=bool(option.state & QStyle.State_Enabled)
        selected=enabled and bool(option.state & (QStyle.State_Selected|QStyle.State_MouseOver))
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(option.rect).adjusted(2,2,-2,-2)
        painter.setPen(Qt.NoPen);painter.setBrush(QColor(p['select'] if selected else p['surface']))
        painter.drawRoundedRect(rect,8,8)
        painter.setPen(QColor(p['text'] if enabled else p['secondary']));painter.setFont(option.font)
        text_rect=rect.adjusted(12,0,-28,0)
        painter.drawText(text_rect,Qt.AlignLeft|Qt.AlignVCenter,option.fontMetrics.elidedText(str(index.data() or ''),Qt.ElideRight,int(text_rect.width())))
        if index.row()==self.combo.currentIndex():
            painter.setPen(QColor(p['accent']));painter.drawText(rect.adjusted(rect.width()-30,0,-8,0),Qt.AlignCenter,'✓')
        painter.restore()


class FluentComboBox(QComboBox):
    """Readable popup rows; scrolling the page must not switch seasons."""
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setMouseTracking(True)
        view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setItemDelegate(ComboItemDelegate(view,self))
        view.setStyleSheet('QListView{padding:0;border:0;outline:0} QListView::item{padding:0;margin:0;min-height:36px}')
        self.setView(view)
        self.setMaxVisibleItems(10)
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self,event):
        if self.isEditable():return super().paintEvent(event)
        option=QStyleOptionComboBox();self.initStyleOption(option);option.currentText=''
        painter=QPainter(self);self.style().drawComplexControl(QStyle.CC_ComboBox,option,painter,self)
        p=palette(QApplication.instance().property('movieboxTheme'));painter.setPen(QColor(p['text'] if self.isEnabled() else p['secondary']));painter.setFont(self.font())
        text_rect=QRectF(self.rect()).adjusted(14,0,-34,0)
        painter.drawText(text_rect,Qt.AlignLeft|Qt.AlignVCenter,self.fontMetrics().elidedText(self.currentText(),Qt.ElideRight,max(0,int(text_rect.width()))))

    def showPopup(self):
        width=min(460,self.screen().availableGeometry().width()-24,max(104,max((self.fontMetrics().horizontalAdvance(self.itemText(i)) for i in range(self.count())),default=0)+50+(10 if self.count()>self.maxVisibleItems() else 0)))
        self.view().setFixedWidth(width-2)
        super().showPopup()
        popup=self.view().window();screen=self.screen().availableGeometry()
        popup.setFixedWidth(width)
        height=min(popup.height(),screen.height()-24)
        point=self.mapToGlobal(QPoint(0,self.height()+6))
        if point.y()+height>screen.bottom():point.setY(self.mapToGlobal(QPoint(0,-height-6)).y())
        popup.setGeometry(max(screen.left()+6,min(point.x(),screen.right()-width-6)),max(screen.top()+6,point.y()),width,height)
        try:
            import ctypes
            motion=ctypes.c_int(1)
            ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(motion),0)
            if not motion.value:popup.setWindowOpacity(1);return
        except (AttributeError,OSError):pass
        if getattr(self,'popup_animation',None):self.popup_animation.stop()
        self.popup_animation=QPropertyAnimation(popup,b'windowOpacity',self)
        self.popup_animation.setDuration(140);self.popup_animation.setStartValue(0.0);self.popup_animation.setEndValue(1.0)
        self.popup_animation.setEasingCurve(QEasingCurve.OutCubic);self.popup_animation.start()

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
        drawer_visible=w.player_episode_panel.isVisible()
        w.player_episode_panel.setParent(self,Qt.Tool|Qt.FramelessWindowHint)
        up_visible=w.next_up_panel.isVisible()
        w.next_up_panel.setParent(self,Qt.Tool|Qt.FramelessWindowHint)
        w.next_up_panel.setAttribute(Qt.WA_ShowWithoutActivating,True)
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
        if up_visible:w.next_up_panel.show();w.next_up_panel.raise_();w.position_next_up()
        if drawer_visible:w.player_episode_panel.show();w.position_player_episodes();w.player_episode_panel.raise_()

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
        up_visible=w.next_up_panel.isVisible()
        drawer_visible=w.player_episode_panel.isVisible()
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
        w.next_up_panel.setParent(w,Qt.Tool|Qt.FramelessWindowHint)
        w.next_up_panel.setAttribute(Qt.WA_ShowWithoutActivating,True)
        if up_visible:w.next_up_panel.show();w.next_up_panel.raise_();w.position_next_up()
        w.player_episode_panel.setParent(w,Qt.Tool|Qt.FramelessWindowHint)
        if drawer_visible:w.player_episode_panel.show();w.position_player_episodes();w.player_episode_panel.raise_()

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
        if not force and self.owner.player_episode_panel.isVisible():
            self.hide_timer.start(1000);return
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
        controls_height = max(78, w.player_controls.sizeHint().height())
        w.player_controls.setGeometry(origin.x() + 20, origin.y() + max(64, height - controls_height - 20), max(100, width - 40), controls_height)
        w.video.position_caption()
        w.position_next_up()
        w.position_player_episodes()

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
        if getattr(w,'closing',False):return False
        stage = getattr(w, 'cinema', None)
        cinema = bool(stage and stage.isVisible())
        mouse_event = event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonDblClick)
        if mouse_event and hasattr(event, 'globalPosition'):
            point = event.globalPosition().toPoint()
            if cinema and stage.frameGeometry().contains(point):
                if event.type() != QEvent.MouseMove or getattr(self, 'last_mouse', None) != point:
                    self.last_mouse = point
                    stage.reveal_controls()
            if isinstance(obj, QWindow) and obj.type() in (Qt.Window,Qt.SubWindow) and event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                video_point = w.video.mapFromGlobal(point)
                panels = (w.player_header, w.player_controls, w.next_up_panel, w.player_episode_panel)
                over_panel = any(p.isVisible() and p.rect().contains(p.mapFromGlobal(point)) for p in panels)
                if w.stack.currentIndex() == 2 and w.video.rect().contains(video_point) and not over_panel:
                    w.video_double_click()
                    return True
        if isinstance(obj, QWidget):
            top = QWidget.window(obj)
            if top is w.volume_menu and event.type()==QEvent.KeyPress:
                focus=QApplication.focusWidget()
                if event.key() in (Qt.Key_Return,Qt.Key_Enter):
                    if isinstance(focus,QAbstractButton):focus.click()
                    else:w.volume_menu.hide();w.mute_button.setFocus()
                    return True
                if event.key()==Qt.Key_Escape:
                    w.volume_menu.hide();w.mute_button.setFocus();return True
                return False
            belongs = top is w or top in (w.next_up_panel,w.player_episode_panel) or (cinema and top in (stage, w.player_header, w.player_controls))
        elif isinstance(obj, QWindow):
            belongs = QApplication.activeWindow() in (w, stage, w.player_header, w.player_controls, w.next_up_panel, w.player_episode_panel)
        else:
            return False
        if not belongs:
            return False
        if event.type()==QEvent.FocusIn and isinstance(obj,(QAbstractButton,QComboBox)) and w.player_controls.isAncestorOf(obj):self.last_player_control=obj
        if event.type()==QEvent.MouseButtonRelease and event.button()==Qt.LeftButton and w.stack.currentIndex()==2:
            if QApplication.activePopupWidget():return False
            point=event.globalPosition().toPoint()
            over_controls=any(panel.isVisible() and panel.rect().contains(panel.mapFromGlobal(point)) for panel in (w.player_header,w.player_controls,w.next_up_panel,w.player_episode_panel))
            inside=w.video.rect().contains(w.video.mapFromGlobal(point))
            source_video=(isinstance(obj,QWindow) and obj.type() in (Qt.Window,Qt.SubWindow)) or (isinstance(obj,QWidget) and (obj is w.video or w.video.isAncestorOf(obj)))
            if source_video and inside and not over_controls:
                w.video_click();event.accept();return True
        if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            inside_video = isinstance(obj, QWidget) and (obj is w.video or w.video.isAncestorOf(obj))
            inside_controls = isinstance(obj, QWidget) and any(obj is panel or panel.isAncestorOf(obj) for panel in (w.player_header, w.player_controls))
            if inside_video and not inside_controls:
                w.video_double_click()
                event.accept()
                return True
        if event.type() != QEvent.KeyPress:
            return False
        key = event.key()
        focus = QApplication.focusWidget()
        if key==Qt.Key_Up and cinema and not stage.controls_visible and w.stack.currentIndex()==2 and not w.player_episode_panel.isVisible() and not QApplication.activePopupWidget() and not isinstance(focus,(QComboBox,QLineEdit,QAbstractSpinBox)) and not w.episode_browser_button.isHidden():
            if not event.isAutoRepeat():w.open_player_episodes()
            return True
        if w.stack.currentIndex()==2 and not QApplication.activePopupWidget() and not w.player_episode_panel.isVisible():
            row=[w.player_transport_layout.itemAt(i).widget() for i in range(w.player_transport_layout.count())]
            row=[item for item in row if isinstance(item,(QAbstractButton,QComboBox)) and item.isVisible() and item.isEnabled()]
            if focus in row and key in (Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down):
                self.last_player_control=focus
                if key in (Qt.Key_Left,Qt.Key_Right):
                    target=row[max(0,min(len(row)-1,row.index(focus)+(1 if key==Qt.Key_Right else -1)))]
                    target.setFocus(Qt.OtherFocusReason);self.last_player_control=target
                elif key==Qt.Key_Up:w.progress.setFocus(Qt.OtherFocusReason)
                return True
            if focus is w.progress and key==Qt.Key_Down and row:
                target=getattr(self,'last_player_control',None)
                (target if target in row else row[0]).setFocus(Qt.OtherFocusReason)
                return True
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
        if cinema or (w.stack.currentIndex()==2 and (w.next_up_panel.isVisible() or w.player_episode_panel.isVisible())):
            if cinema:stage.reveal_controls()
            if key in (Qt.Key_Tab, Qt.Key_Backtab):
                controls = []
                for panel in ((w.player_episode_panel,) if w.player_episode_panel.isVisible() else (w.player_header, w.player_controls, w.next_up_panel)):
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
        if focus and w.player_episode_panel.isAncestorOf(focus):return False
        typing = isinstance(focus, (QLineEdit, QAbstractSpinBox, QComboBox))
        if w.stack.currentIndex() == 2 and not typing and not isinstance(focus, QAbstractButton):
            if key == Qt.Key_Space:
                w.toggle_pause()
                return True
            if key in (Qt.Key_Left, Qt.Key_Right) and not isinstance(focus, QSlider):
                w.seek_to(w.player.position() + (10000 if key == Qt.Key_Right else -10000))
                return True
        return False
