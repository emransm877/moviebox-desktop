"""Compact, keyboard-accessible native preferences with live theme previews."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QFont, QPen
from PySide6.QtWidgets import (QApplication, QDialog, QWidget, QLabel, QFrame,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QButtonGroup, QSpinBox, QCheckBox, QSizePolicy)
from themes import THEMES, initial_theme, palette
from interactions import FluentComboBox


class ThemePreviewButton(QPushButton):
    def __init__(self,key,scroller):
        super().__init__()
        self.key,self.scroller=key,scroller
        self.setObjectName('themeOption-'+key)
        self.setAccessibleName(THEMES[key]['name'])
        self.setAccessibleDescription(THEMES[key]['description'])
        self.setToolTip(THEMES[key]['name']+'\n'+THEMES[key]['description'])
        self.setCheckable(True);self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumWidth(100);self.setFixedHeight(84)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

    def focusInEvent(self,event):
        super().focusInEvent(event)
        self.scroller.ensureWidgetVisible(self,10,10)
        self.update()

    def paintEvent(self,event):
        p=THEMES[self.key];current=palette(QApplication.instance().property('movieboxTheme'))
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(p['accent'] if self.isChecked() or self.hasFocus() else current['line']),2 if self.isChecked() or self.hasFocus() else 1))
        painter.setBrush(QColor(current['select'] if self.isChecked() else current['surface']))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2),9,9)
        preview=QRectF(10,9,self.width()-20,38)
        painter.setPen(Qt.NoPen);painter.setBrush(QColor(p['base']));painter.drawRoundedRect(preview,4,4)
        painter.setBrush(QColor(p['panel']));painter.drawRect(QRectF(preview.left(),preview.top(),preview.width()*.19,preview.height()))
        painter.setBrush(QColor(p['accent']));painter.drawRoundedRect(QRectF(preview.left()+4,preview.top()+7,preview.width()*.1,3),1,1)
        painter.setBrush(QColor(p['surface']));painter.drawRoundedRect(QRectF(preview.left()+preview.width()*.25,preview.top()+5,preview.width()*.68,13),2,2)
        for i in range(4):
            painter.setBrush(QColor(p['accent'] if i==1 else p['hover']))
            painter.drawRoundedRect(QRectF(preview.left()+preview.width()*(.25+i*.18),preview.top()+23,preview.width()*.14,10),1,1)
        font=QFont(self.font());font.setPixelSize(11);font.setWeight(QFont.DemiBold if self.isChecked() else QFont.Normal)
        painter.setFont(font);painter.setPen(QColor(current['text']))
        name=p['name'].replace(' Cinema','')
        painter.drawText(QRectF(7,50,self.width()-14,29),Qt.AlignHCenter|Qt.AlignVCenter|Qt.TextWordWrap,name)


def build_settings_dialog(window):
    from fluent_ui import action,refresh_theme,apply_window_material,system_is_dark
    dialog=QDialog(window);dialog.setObjectName('settingsDialog');dialog.setWindowTitle('MovieBox settings')
    available=window.screen().availableGeometry()
    dialog.setMinimumWidth(min(620,available.width()-48))
    dialog.resize(min(720,available.width()-48),min(610,available.height()-64))
    outer=QVBoxLayout(dialog);outer.setContentsMargins(22,18,22,16);outer.setSpacing(12)
    header=QHBoxLayout();title=QLabel('Settings');title.setObjectName('settingsTitle');title.setStyleSheet('font-size:26px;font-weight:650')
    header.addWidget(title);header.addStretch();saved=QLabel('Changes save automatically');saved.setObjectName('muted');saved.setStyleSheet('font-size:12px');header.addWidget(saved);outer.addLayout(header)
    scroll=QScrollArea();scroll.setObjectName('settingsScroll');scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    body=QWidget();scroll.setWidget(body);layout=QVBoxLayout(body);layout.setContentsMargins(0,0,10,0);layout.setSpacing(14);layout.setAlignment(Qt.AlignTop);outer.addWidget(scroll,1)
    section=QHBoxLayout();label=QLabel('Theme');label.setStyleSheet('font-size:15px;font-weight:600');section.addWidget(label);section.addStretch()
    count=QLabel(str(len(THEMES))+' styles · Live preview');count.setObjectName('muted');count.setStyleSheet('font-size:12px');section.addWidget(count);layout.addLayout(section)
    theme_scroll=QScrollArea();theme_scroll.setObjectName('themeScroll');theme_scroll.setWidgetResizable(True);theme_scroll.setFrameShape(QFrame.NoFrame);theme_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    theme_body=QWidget();theme_body.setObjectName('themePicker');grid=QGridLayout(theme_body);grid.setContentsMargins(0,0,6,0);grid.setSpacing(7);theme_scroll.setWidget(theme_body)
    theme_scroll.setFixedHeight(min(2,(len(THEMES)+4)//5)*91+2)
    group=QButtonGroup(dialog);group.setExclusive(True);buttons={}
    modes=list(THEMES);selected=initial_theme(window.state,system_is_dark())
    for i,key in enumerate(modes):
        button=ThemePreviewButton(key,theme_scroll);buttons[key]=button;group.addButton(button,i);grid.addWidget(button,i//5,i%5);button.setChecked(key==selected)
    layout.addWidget(theme_scroll)
    hint=QLabel(THEMES[selected]['description']);hint.setObjectName('themeHint');hint.setWordWrap(True);hint.setStyleSheet('font-size:12px');hint.setMaximumHeight(35);layout.addWidget(hint)
    appearance_row=QHBoxLayout();appearance_label=QLabel('Appearance');appearance_label.setMinimumWidth(115);appearance_row.addWidget(appearance_label)
    appearance=FluentComboBox();appearance.setObjectName('appearancePicker');appearance.setAccessibleName('Appearance')
    appearance_modes=['theme','dark','light','system'];appearance.addItems(['Use theme colours','Dark','Light','Follow Windows'])
    appearance.setCurrentIndex(appearance_modes.index(window.state.get('appearance','theme')) if window.state.get('appearance','theme') in appearance_modes else 0)
    appearance_row.addWidget(appearance,1);layout.addLayout(appearance_row)
    def select_theme(key):
        window.state['theme']=key;window.state['appearance']='theme'
        appearance.blockSignals(True);appearance.setCurrentIndex(0);appearance.blockSignals(False)
        buttons[key].setChecked(True);hint.setText(THEMES[key]['description'])
        refresh_theme(window,key);apply_window_material(dialog,THEMES[key]['dark']);window.persist()
    for key,button in buttons.items():button.clicked.connect(lambda checked=False,key=key:select_theme(key))
    def select_appearance(index):
        mode=appearance_modes[index];window.state['appearance']=mode
        if mode!='theme':
            key='aurora' if mode=='light' or (mode=='system' and not system_is_dark()) else 'obsidian'
            window.state['theme']=key;buttons[key].setChecked(True);hint.setText(THEMES[key]['description'])
        key=window.state.get('theme','obsidian');refresh_theme(window,key);apply_window_material(dialog,THEMES[key]['dark']);window.persist()
    appearance.currentIndexChanged.connect(select_appearance)
    subtitle_row=QHBoxLayout();subtitle_label=QLabel('Subtitle size');subtitle_label.setMinimumWidth(115);subtitle_row.addWidget(subtitle_label)
    size=QSpinBox();size.setObjectName('subtitleSize');size.setAccessibleName('Subtitle text size');size.setRange(16,44);size.setSuffix(' px');size.setValue(int(window.state.get('subtitle_size',24)));size.setFixedWidth(118)
    size.lineEdit().setTextMargins(10,0,4,0);size.lineEdit().setAlignment(Qt.AlignLeft|Qt.AlignVCenter);subtitle_row.addWidget(size)
    preview=QLabel('MovieBox');preview.setObjectName('subtitlePreview');preview.setAlignment(Qt.AlignCenter);preview.setFixedHeight(72);preview.setMinimumWidth(210);subtitle_row.addWidget(preview,1);layout.addLayout(subtitle_row)
    def set_size(value,persist=True):
        style=f'background:rgba(0,0,0,180);color:white;font-size:{value}px;font-weight:600;padding:7px;border-radius:7px'
        preview.setStyleSheet(style)
        if persist:window.state['subtitle_size']=value;window.persist();window.video.caption.setStyleSheet(style)
    set_size(size.value(),False);size.valueChanged.connect(set_size)
    updates_row=QHBoxLayout();updates=QCheckBox('Optional update alerts');updates.setObjectName('updateNotifications');updates.setAccessibleName('Notify me about optional MovieBox updates');updates.setChecked(window.state['update_notifications'].get('enabled',True));updates.toggled.connect(window.configure_optional_updates);updates_row.addWidget(updates);updates_row.addStretch()
    check=action('Check now',lambda:window.check_optional_updates(force=True));check.setObjectName('checkUpdates');check.setAccessibleName('Check for updates');check.setEnabled(updates.isChecked());updates.toggled.connect(check.setEnabled);updates_row.addWidget(check);layout.addLayout(updates_row)
    shortcuts=QLabel('F11  Fullscreen     Esc  Back     Ctrl+K  Search     ↑/↓  Volume');shortcuts.setObjectName('keyboardHints');shortcuts.setWordWrap(True);shortcuts.setStyleSheet('font-size:12px');layout.addWidget(shortcuts)
    layout.addStretch(1)
    footer=QHBoxLayout();footer.addStretch();done=action('Done',dialog.accept,primary=True);done.setObjectName('settingsDone');done.setMinimumWidth(104);footer.addWidget(done);outer.addLayout(footer)
    order=list(buttons.values())+[appearance,size,updates,check,done]
    for previous,next_widget in zip(order,order[1:]):QWidget.setTabOrder(previous,next_widget)
    dialog.theme_buttons=buttons;dialog.theme_group=group
    apply_window_material(dialog,bool(QApplication.instance().property('movieboxDark')))
    return dialog
