"""Bounded native QPainter poster planes using the shared 20-theme geometry."""
from collections import OrderedDict,deque
import math,time,os,ctypes
from PySide6.QtCore import Qt,QPointF,QRectF,QTimer,QVariantAnimation,QAbstractAnimation,QEasingCurve,Signal
from PySide6.QtGui import QPainter,QPainterPath,QColor,QPen,QPolygonF,QTransform,QFont
from PySide6.QtWidgets import QWidget,QApplication
from themes import THEMES,THEME_EFFECTS,THEME_SPEC
from artwork_layout import fill_source_rect


class SpatialHero(QWidget):
    selected=Signal(object)
    activated=Signal(object)

    def __init__(self,owner,parent):
        super().__init__(parent)
        self.owner=owner;self.art=owner.art;self.subjects=[];self.index=0;self.actors=[];self.polygons=[];self.cache=OrderedDict()
        self.progress=1.;self.queued=0;self.direction=1;self.key='';self.geometry_spec={};self.frame_times=deque(maxlen=180)
        self.metrics={'frames':0,'maxPlanes':0,'maxCacheEntries':0,'maxPaintMs':0,'sourceRequests':0}
        self.setFocusPolicy(Qt.StrongFocus);self.setAccessibleName('Featured titles');self.setMouseTracking(True)
        self.setAccessibleDescription('Left and Right browse titles. Enter opens details. Space pauses automatic movement. Drag horizontally or use horizontal wheel to browse.')
        self.press_point=None;self.press_subject=None;self.wheel_distance=0;self.last_manual=0.
        self.animation=QVariantAnimation(self);self.animation.setDuration(840);self.animation.setStartValue(0.);self.animation.setEndValue(1.);self.animation.setEasingCurve(QEasingCurve.Linear)
        self.animation.valueChanged.connect(self.frame);self.animation.finished.connect(self.complete)
        self.auto=QTimer(self);self.auto.setSingleShot(True);self.auto.timeout.connect(self.automatic)
        self.art.changed.connect(self.update);self.apply_theme()

    def motion_allowed(self):
        if not getattr(getattr(self.owner,'poster_delegate',None),'motion',True):return False
        if os.name=='nt':
            enabled=ctypes.c_int(1)
            try:
                if ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(enabled),0):return bool(enabled.value)
            except (AttributeError,OSError):pass
        return True

    def apply_theme(self):
        self.key=QApplication.instance().property('movieboxTheme') or 'obsidian'
        self.geometry_spec=THEME_EFFECTS[self.key];self.animation.stop();self.progress=1.;self.queued=0
        self.actors=[];self.arrange(False);self.update();self.schedule(2000)

    def set_subjects(self,subjects,identity=None):
        previous=[str(s.get('subjectId')) for s in self.subjects];current=[str(s.get('subjectId')) for s in subjects]
        self.subjects=list(subjects[:100])
        if identity is not None:self.index=next((i for i,s in enumerate(self.subjects) if str(s.get('subjectId'))==str(identity)),0)
        self.index=min(self.index,max(0,len(self.subjects)-1))
        if current!=previous:self.animation.stop();self.actors=[];self.progress=1.;self.arrange(False)
        elif self.actors and self.actors[0].get('_selected_index')!=self.index:self.arrange(True)
        self.update();self.schedule(2000)

    def arrange(self,animated):
        if not self.subjects:return
        slots=self.geometry_spec['slots']
        if len(self.subjects)<len(slots):slots=sorted(slots,key=lambda s:abs(s['offset']))[:len(self.subjects)]
        old=list(self.actors);unused=list(old);planned=[]
        for slot in slots:
            target=(self.index+int(slot['offset']))%len(self.subjects);subject=self.subjects[target];identity=str(subject['subjectId'])
            actor=next((a for a in unused if str(a['subject']['subjectId'])==identity),None)
            if actor:unused.remove(actor)
            planned.append((slot,subject,actor))
        actors=[]
        for slot,subject,actor in planned:
            recycled=actor is None and bool(unused)
            if actor is None:actor=unused.pop(0) if unused else {'subject':subject,'slot':dict(slot)}
            actors.append({'subject':subject,'old_subject':actor['subject'],'from':dict(actor.get('slot',slot)),'slot':dict(slot),'recycled':recycled,'_selected_index':self.index})
        self.actors=actors;self.progress=0. if animated and self.motion_allowed() else 1.
        # Only visible planes plus two adjacent subjects are requested.
        visible=[a['subject'] for a in actors]
        for offset in [-1,1]:
            outer=max(abs(int(s['offset'])) for s in slots)+1
            visible.append(self.subjects[(self.index+offset*outer)%len(self.subjects)])
        for subject in visible:self.poster(subject)
        if self.progress<1:self.animation.start()

    def select(self,index,manual=True):
        if not self.subjects:return
        if manual:self.last_manual=time.monotonic();self.schedule(8000)
        if self.animation.state()==QAbstractAnimation.State.Running:
            if manual:self.queued=index-self.index
            return
        delta=index-self.index
        if abs(delta)>len(self.subjects)/2:delta-=int(math.copysign(len(self.subjects),delta))
        self.direction=1 if delta>=0 else -1
        self.index=index%len(self.subjects);self.arrange(True);self.selected.emit(self.subjects[self.index]);self.setAccessibleName('Featured title: '+self.subjects[self.index].get('title',''));self.update()
        if manual:self.schedule(8000)

    def advance(self,step,manual=True):self.select(self.index+step,manual)

    def frame(self,value):
        if getattr(self.owner,'closing',False):self.animation.stop();self.auto.stop();return
        if not self.motion_allowed():self.animation.stop();self.progress=1.;self.queued=0;self.complete();return
        self.progress=float(value);self.update()

    def complete(self):
        self.progress=1.
        for actor in self.actors:actor['old_subject']=actor['subject'];actor['from']=dict(actor['slot']);actor['recycled']=False
        self.update()
        if self.queued:step=self.queued;self.queued=0;self.advance(step)
        else:self.schedule(6000-self.animation.duration())

    def schedule(self,delay):
        idle_remaining=8-(time.monotonic()-self.last_manual)
        if idle_remaining>0:delay=max(1,math.ceil(idle_remaining*1000))
        if self.subjects and self.isVisible() and self.motion_allowed() and not self.parentWidget().rotation_paused:self.auto.start(delay)
        else:self.auto.stop()

    def automatic(self):
        parent=self.parentWidget()
        if getattr(self.owner,'closing',False) or not self.isVisible() or parent.rotation_paused or not self.motion_allowed():return
        if time.monotonic()-self.last_manual<8:
            self.schedule(max(100,int((8-(time.monotonic()-self.last_manual))*1000)));return
        if not self.owner.isActiveWindow() or self.owner.stack.currentIndex()!=0:
            self.schedule(6000);return
        self.advance(1,False)

    def showEvent(self,event):super().showEvent(event);self.schedule(2000)
    def focusInEvent(self,event):
        super().focusInEvent(event)
    def focusOutEvent(self,event):
        super().focusOutEvent(event)
    def hideEvent(self,event):
        self.auto.stop();self.animation.stop();self.progress=1.;self.queued=0
        for actor in self.actors:actor['old_subject']=actor['subject'];actor['from']=dict(actor['slot']);actor['recycled']=False
        super().hideEvent(event)

    def poster(self,subject):
        if getattr(self.owner,'closing',False):return None
        url=(subject.get('cover') or {}).get('url')
        if not url:return None
        if url in self.cache:self.cache.move_to_end(url);return self.cache[url]
        image=self.art.get(url)
        if image is not None:
            self.cache[url]=image
            while len(self.cache)>24:self.cache.popitem(last=False)
            self.metrics['maxCacheEntries']=max(self.metrics['maxCacheEntries'],len(self.cache))
        return image

    def current(self,actor):
        p=self.progress;start,target=actor['from'],actor['slot']
        if p>=1:return target,actor['subject']
        if actor['recycled']:
            if p<.22:
                q=p/.22;s=dict(start);s['x']-=self.direction*.085*q;s['z']-=.127*q;s['opacity']=start['opacity']*(1-q)
                return s,actor['old_subject']
            q=(p-.22)/.78;q=1-(1-q)**3;enter=dict(target);enter['x']+=(1 if target['x']>=0 else -1)*.089;enter['z']-=.153;enter['scale']*=.87
            s={k:enter[k]+(target[k]-enter[k])*q for k in ['x','y','z','rotateX','rotateY','rotateZ','scale','opacity']};s['opacity']=target['opacity']*q
            return s,actor['subject']
        q=1-(1-p)**3;s={k:start[k]+(target[k]-start[k])*q for k in ['x','y','z','rotateX','rotateY','rotateZ','scale','opacity']}
        lift=math.sin(math.pi*p);s['z']+=.055*lift;s['y']-=.035*lift;s['rotateX']-=7*lift;s['rotateZ']-=3*lift
        return s,actor['subject']

    def polygon(self,slot):
        reference=THEME_SPEC['reference'];factor=min(self.width()/reference['stageWidth'],self.height()/reference['stageHeight'])
        width,height=reference['posterWidth']*factor,reference['posterHeight']*factor
        perspective=self.geometry_spec['perspective']*self.width();points=[]
        order=[op for op in self.geometry_spec['rotationOrder'] if op.startswith('rotate')][::-1]
        for x,y in [(-width/2,-height/2),(width/2,-height/2),(width/2,height/2),(-width/2,height/2)]:
            x*=slot['scale'];y*=slot['scale'];z=0
            for op in order:
                angle=math.radians(slot[op]);c,s=math.cos(angle),math.sin(angle)
                if op=='rotateX':y,z=y*c-z*s,y*s+z*c
                elif op=='rotateY':x,z=x*c+z*s,-x*s+z*c
                else:x,y=x*c-y*s,x*s+y*c
            x+=slot['x']*self.width();y+=slot['y']*self.height();z+=slot['z']*self.width()
            projection=perspective/max(1,perspective-z)
            points.append(QPointF(self.width()/2+x*projection,self.height()/2+y*projection))
        return QPolygonF(points),width,height

    def paintEvent(self,event):
        started=time.perf_counter();p=THEMES[self.key];painter=QPainter(self);painter.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
        # A restrained floor anchors all twenty spatial arrangements.
        floor=QColor(p['accent']);floor.setAlpha(45);painter.setPen(QPen(floor,1));painter.drawLine(24,self.height()-8,self.width()-24,self.height()-8)
        self.polygons=[];planes=[]
        for actor in self.actors:
            slot,subject=self.current(actor);planes.append((slot['z'],slot,subject))
        for _,slot,subject in sorted(planes,key=lambda row:row[0]):
            polygon,width,height=self.polygon(slot);self.polygons.append((polygon,subject));painter.save();painter.setOpacity(max(0,min(1,slot['opacity'])))
            painter.setPen(Qt.NoPen);painter.setBrush(QColor(0,0,0,65));painter.drawPolygon(QPolygonF([point+QPointF(0,5) for point in polygon]))
            mapping=QTransform();source=QPolygonF([QPointF(0,0),QPointF(width,0),QPointF(width,height),QPointF(0,height)])
            if not QTransform.quadToQuad(source,polygon,mapping):painter.restore();continue
            painter.setTransform(mapping);rect=QRectF(0,0,width,height);path=QPainterPath();path.addRoundedRect(rect,5,5);painter.setClipPath(path)
            painter.fillRect(rect,QColor(p['surface']));image=self.poster(subject)
            if image is not None:painter.drawPixmap(rect,image,QRectF(*fill_source_rect(image.width(),image.height(),width,height)))
            else:
                font=QFont('Segoe UI');font.setPixelSize(max(8,int(width*.085)));painter.setFont(font);painter.setPen(QColor(p['text']));painter.drawText(rect.adjusted(7,7,-7,-7),Qt.AlignCenter|Qt.TextWordWrap,subject.get('title',''))
            active=self.subjects and str(subject['subjectId'])==str(self.subjects[self.index]['subjectId'])
            painter.setClipping(False);painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor(p['accent'] if active else p['line']),2 if active else 1));painter.drawRoundedRect(rect.adjusted(1,1,-1,-1),5,5);painter.restore()
        painter.end();elapsed=(time.perf_counter()-started)*1000;self.frame_times.append(elapsed);self.metrics['frames']+=1;self.metrics['maxPlanes']=max(self.metrics['maxPlanes'],len(planes));self.metrics['maxPaintMs']=max(self.metrics['maxPaintMs'],elapsed)

    def memory_metrics(self):
        return {'entries':len(self.cache),'max_entries':24,'decoded_bytes_upper_bound':sum(image.width()*image.height()*4 for image in self.cache.values()),'max_decoded_width':max((image.width() for image in self.cache.values()),default=0),'max_decoded_height':max((image.height() for image in self.cache.values()),default=0)}

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason);self.last_manual=time.monotonic();self.schedule(8000);self.press_point=event.position();self.press_subject=None
            for polygon,subject in reversed(self.polygons):
                if polygon.containsPoint(event.position(),Qt.OddEvenFill):
                    self.press_subject=subject;break
            event.accept();return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.press_point is not None:
            delta=event.position()-self.press_point;subject=self.press_subject;self.press_point=None;self.press_subject=None
            if abs(delta.x())>8 and abs(delta.x())>=abs(delta.y()):self.advance(-1 if delta.x()>0 else 1)
            elif abs(delta.x())<=8 and abs(delta.y())<=8 and subject:self.activated.emit(subject)
            event.accept();return
        super().mouseReleaseEvent(event)

    def wheelEvent(self,event):
        horizontal=event.pixelDelta().x() or event.angleDelta().x()
        if not horizontal and event.modifiers()&Qt.ShiftModifier:horizontal=event.pixelDelta().y() or event.angleDelta().y()
        if not horizontal:event.ignore();return
        self.last_manual=time.monotonic();self.schedule(8000)
        self.wheel_distance+=horizontal
        if abs(self.wheel_distance)>=40:self.advance(-1 if self.wheel_distance>0 else 1);self.wheel_distance=0
        event.accept()

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Left,Qt.Key_Right):self.advance(1 if event.key()==Qt.Key_Right else -1);event.accept()
        elif event.key() in (Qt.Key_Return,Qt.Key_Enter):
            self.last_manual=time.monotonic()
            if self.subjects:self.activated.emit(self.subjects[self.index])
            event.accept()
        elif event.key()==Qt.Key_Space:
            self.parentWidget().toggle_rotation()
            if not self.parentWidget().rotation_paused:self.last_manual=0.;self.schedule(2000)
            event.accept()
        else:super().keyPressEvent(event)
