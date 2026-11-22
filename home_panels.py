"""A compact home strip backed exclusively by the existing playback history."""
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QColor,QFont,QPen
from PySide6.QtWidgets import QWidget,QPushButton,QLabel,QHBoxLayout,QVBoxLayout,QApplication
from themes import palette
from artwork_layout import fill_source_rect


def clock(milliseconds):
    seconds=max(0,int(milliseconds or 0)//1000);hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
    return f'{hours}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes}:{seconds:02d}'


def recent_history(history,limit=3):
    if limit<=0:return []
    def updated(pair):
        try:return float(pair[1].get('updated') or 0)
        except (TypeError,ValueError):return 0
    chosen=[];seen=set()
    for key,record in sorted(((k,v) for k,v in history.items() if isinstance(v,dict)),key=updated,reverse=True):
        subject=record.get('subject') or {}
        if not isinstance(subject,dict):continue
        identity=str(subject.get('subjectId') or '')
        if not isinstance(key,str) or len(key.rsplit(':',2))!=3:continue
        _,season,episode=key.rsplit(':',2)
        if not season.isdigit() or not episode.isdigit():continue
        try:position,duration=int(record.get('position') or 0),int(record.get('duration') or 0)
        except (TypeError,ValueError):continue
        if not identity or identity in seen or position<=0 or duration<=0 or record.get('completed') or position>=duration*.98:continue
        seen.add(identity);chosen.append((key,dict(record,position=position,duration=duration)))
        if len(chosen)>=limit:break
    return chosen


class ContinueCard(QPushButton):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.record=None;self.key='';self.compact=False
        self.setCursor(Qt.PointingHandCursor);self.setFocusPolicy(Qt.StrongFocus);self.setMinimumWidth(150);self.setFixedHeight(72)
        self.clicked.connect(lambda:self.owner.continue_from_history(self.key))

    def set_record(self,key,record):
        self.key,self.record=key,record;title=record['subject'].get('title','')
        self.setAccessibleName('Continue '+title+', '+clock(record['position'])+' of '+clock(record['duration']))
        self.setToolTip(title+' · '+clock(record['position'])+' / '+clock(record['duration']));self.update()

    def paintEvent(self,event):
        if not self.record:return
        p=palette(QApplication.instance().property('movieboxTheme'));painter=QPainter(self);painter.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
        painter.setPen(QPen(QColor(p['accent'] if self.hasFocus() else p['line']),1));painter.setBrush(QColor(p['hover'] if self.underMouse() else p['surface']));painter.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),9,9)
        thumb=QRectF(8,6,32 if self.compact else 40,self.height()-12);text_left=thumb.right()+11
        image=self.owner.art.get((self.record['subject'].get('cover') or {}).get('url',''))
        if image is not None:painter.drawPixmap(thumb,image,QRectF(*fill_source_rect(image.width(),image.height(),thumb.width(),thumb.height())))
        title=self.record['subject'].get('title','');font=QFont('Segoe UI');font.setPixelSize(12);font.setWeight(QFont.DemiBold);painter.setFont(font);painter.setPen(QColor(p['text']))
        painter.drawText(QRectF(text_left,8,self.width()-text_left-10,18),Qt.AlignLeft|Qt.AlignVCenter,painter.fontMetrics().elidedText(title,Qt.ElideRight,int(self.width()-text_left-10)))
        font.setPixelSize(10);font.setWeight(QFont.Normal);painter.setFont(font);painter.setPen(QColor(p['secondary']))
        _,season,episode=self.key.rsplit(':',2);prefix=f'S{season} E{episode} · ' if season!='0' else ''
        painter.drawText(QRectF(text_left,27,self.width()-text_left-10,16),Qt.AlignLeft|Qt.AlignVCenter,prefix+clock(self.record['position'])+' / '+clock(self.record['duration']))
        bar=QRectF(text_left,self.height()-10,max(1,self.width()-text_left-12),3);painter.fillRect(bar,QColor(p['line']));bar.setWidth(bar.width()*min(1,self.record['position']/self.record['duration']));painter.fillRect(bar,QColor(p['accent']))


class ContinueStrip(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setObjectName('continueWatchingStrip')
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(7)
        row=QHBoxLayout();label=QLabel('Continue watching');label.setStyleSheet('font-size:16px;font-weight:600');row.addWidget(label);row.addStretch()
        view=QPushButton('View all');view.setObjectName('quiet');view.setAccessibleName('View all playback history');view.setStyleSheet('padding:3px 7px;font-size:12px');view.clicked.connect(owner.show_history);row.addWidget(view);layout.addLayout(row)
        cards=QHBoxLayout();cards.setSpacing(10);self.cards=[ContinueCard(owner) for _ in range(3)]
        for card in self.cards:cards.addWidget(card,1)
        layout.addLayout(cards);self.setFixedHeight(104);self.hide();owner.art.changed.connect(self.update_cards)

    def update_cards(self):
        if self.isVisible():
            for card in self.cards:card.update()

    def refresh(self):
        records=recent_history(self.owner.state.get('history') or {})
        home=self.owner.nav_buttons.get('home')
        self.setVisible(bool(records) and bool(home and home.isChecked()) and self.owner.stack.currentIndex()==0)
        for i,card in enumerate(self.cards):
            card.setVisible(i<len(records))
            if i<len(records):card.set_record(*records[i])

    def set_compact(self,compact):
        self.setFixedHeight(90 if compact else 104)
        for card in self.cards:card.compact=compact;card.setFixedHeight(58 if compact else 72)
