"""Isolated native Qt artwork/control verification using captured own-title images."""
import argparse
import copy
import json
import os
from pathlib import Path
import threading
import time
from unittest.mock import patch

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--artwork',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR']=str(args.output/'isolated-userdata')

from PySide6.QtCore import Qt, QSize, QPoint, QRect
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem
from main import Window, Artwork
from fluent_ui import refresh_theme, stylesheet
from artwork_layout import prepare_artwork


class API:
    native=None
    account_token=''
    last_play_info={}


app=QApplication([])
app.setStyleSheet(stylesheet('obsidian'))
checks={};geometry={};timings={};passed=False
wide=json.loads((args.artwork/'actual-movie-shapes.json').read_text(encoding='utf-8'))
square=json.loads((args.artwork/'actual-square-cover.json').read_text(encoding='utf-8'))['found'][0]
subjects=[wide['wide']['subject'],wide['tall']['subject'],square]
images=[args.artwork/'actual-movie-wide.webp',args.artwork/'actual-movie-tall.webp',args.artwork/'actual-square-cover.webp']
with patch.object(Window,'load_home',lambda self:None),patch.object(Window,'check_optional_updates',lambda *args,**kwargs:None):w=Window(API())
w.update_timer.stop();w.schedule_prefetch=lambda:None
w.hero.hide();w.resize(1440,900);w.show();w.activateWindow();QTest.qWait(150)
for subject,image in zip(subjects,images):w.art.images[subject['cover']['url']]=QPixmap(str(image))

try:
    for theme in ['obsidian','orbital','prism','aurora','eclipse']:
        app.setProperty('movieboxTheme',theme);refresh_theme(w,theme)
        w.poster_delegate.motion=False
        w.hero.set_slides(subjects);w.hero.show();w.stack.setCurrentIndex(0)
        for label,subject in zip(['wide','near-portrait','square'],subjects):
            w.hero.set_subject(subject);app.processEvents()
            scene=w.hero.spatial
            assert scene.subjects[scene.index]['subjectId']==subject['subjectId']
            assert scene.poster(subject) is not None
            assert len(scene.actors)==3
            assert not w.hero.findChildren(__import__('PySide6.QtWidgets',fromlist=['QPushButton']).QPushButton)
            w.hero.grab().save(str(args.output/(theme+'-hero-'+label+'-filled-poster.png')))
            checks[theme+'_'+label+'_own_poster_native_scene_without_extra_controls']=True
        w.hero.hide()
        for label,items,ratio in [('wide',[subjects[0]]*12,16/9),('portrait',[subjects[1]]*12,2/3),('mixed',subjects*4,1)]:
            # Keep actual artwork/title association; duplicate IDs only for layout fixtures.
            items=[dict(item,subjectId=item['subjectId']+'-fixture-'+str(i)) for i,item in enumerate(items)]
            w.request_generation+=1;w.show_items(items);QTest.qWait(100)
            assert w.poster_delegate.sizeHint(None,None)==QSize(184,316)
            rects=[w.grid.visualRect(w.catalog_model.index(i,0)) for i in range(len(items))]
            assert len({(r.width(),r.height()) for r in rects})==1
            for r in rects:
                cover=w.poster_delegate.cover_rect(r)
                assert abs(cover.width()/cover.height()-172/238)<.01
            original=rects[0].size();w.show_items(items+[dict(subjects[1],subjectId='later-'+str(i)) for i in range(12)])
            QTest.qWait(30);assert w.poster_delegate.sizeHint(None,None)==QSize(184,316)
            assert w.grid.visualRect(w.catalog_model.index(0,0)).size()==original
            checks[theme+'_'+label+'_equal_frames_locked_through_more']=True
            geometry[theme+'_'+label]={'aspect':172/238,'tile':[original.width(),original.height()]}
            w.grab().save(str(args.output/(theme+'-'+label+'.png')))
        for count in [1,8]:
            w.stack.setCurrentIndex(1);w.season_row.show();w.season.show()
            w.season.blockSignals(True);w.season.clear()
            for i in range(count):w.season.addItem('Season '+str(i+1),{'se':i+1})
            w.season.fit_contents();w.season.blockSignals(False);QTest.qWait(20)
            expected=max(w.season.fontMetrics().horizontalAdvance(w.season.itemText(i)) for i in range(count))+50
            assert w.season.width()<=expected+2
            w.season.showPopup();QTest.qWait(160)
            assert w.season.view().window().width()<=expected+2,(theme,count,expected,w.season.view().window().width(),w.season.view().width())
            checks[theme+'_season_'+str(count)+'_compact_control_and_popup']=True
            w.grab().save(str(args.output/(theme+'-season-'+str(count)+'.png')))
            w.season.hidePopup()
    w.stack.setCurrentIndex(2);w.activateWindow();QTest.qWait(40);w.video.setFocus();QTest.qWait(20);w.audio.setMuted(False);w.volume.setValue(70)
    QTest.keyClick(w.video,Qt.Key_Up);assert w.volume.value()==75
    QTest.keyClick(w.video,Qt.Key_Down);assert w.volume.value()==70
    w.volume.setValue(100);QTest.keyClick(w.video,Qt.Key_Up);assert w.volume.value()==100
    w.volume.setValue(0);QTest.keyClick(w.video,Qt.Key_Down);assert w.volume.value()==0
    w.audio.setMuted(True);QTest.keyClick(w.video,Qt.Key_Up);assert not w.audio.isMuted() and w.volume.value()==5
    checks['playback_arrows_volume_clamp_and_unmute']=True
    w.quality.setFocus();before=w.volume.value();QTest.keyClick(w.quality,Qt.Key_Down);assert w.volume.value()==before
    w.mute_button.setFocus();QTest.keyClick(w.mute_button,Qt.Key_Up);assert w.volume.value()==before and app.focusWidget() is w.progress
    w.player_episode_panel.show();w.player_episode_list.setFocus();QTest.keyClick(w.player_episode_list,Qt.Key_Down);assert w.volume.value()==before
    w.player_episode_panel.hide();checks['menu_transport_and_episode_navigation_preserve_volume']=True
    w.playing_subject={'subjectId':'owned-series','subjectType':2,'title':'Owned series'}
    w.playing_key='owned-series:1:1'
    w.detail_data={'resource':{'seasons':[{'se':1,'maxEp':6}]}}
    w.episode_browser_button.show()
    w.open_player_episodes();QTest.qWait(180)
    panel=w.player_episode_panel
    assert panel.height()<w.video.height()-30,(panel.height(),w.video.height())
    assert w.player_episode_list.height()<=6*48+4
    assert w.player_season_picker.width()<130
    assert 220<=panel.width()<=300
    geometry['six_episode_drawer']={'panelWidth':panel.width(),'panelHeight':panel.height(),'videoHeight':w.video.height(),'listHeight':w.player_episode_list.height()}
    panel.grab().save(str(args.output/'six-episode-drawer.png'))
    checks['six_episode_drawer_uses_content_height_and_compact_season']=True
    with patch.object(w,'video_click') as clicked:
        QTest.mouseClick(w.video,Qt.LeftButton,pos=w.video.rect().topLeft()+QPoint(12,12))
        assert not panel.isVisible() and not clicked.called
    checks['outside_click_dismisses_without_video_click_through']=True
    w.detail_data['resource']['seasons'][0]['maxEp']=100
    w.open_player_episodes();QTest.qWait(180)
    assert panel.height()<=w.video.height()-24,(panel.height(),w.video.height(),w.player_episode_list.height(),panel.layout().sizeHint().height(),panel.minimumHeight(),[(panel.layout().itemAt(i).sizeHint().height(),panel.layout().itemAt(i).heightForWidth(396)) for i in range(panel.layout().count())])
    assert w.player_episode_list.verticalScrollBar().maximum()>0
    checks['long_episode_list_scrolls_within_video_bounds']=True
    w.close_player_episodes();w.detail_data['resource']['seasons'][0]['maxEp']=6
    w.toggle_fullscreen();QTest.qWait(150);w.cinema.hide_controls(force=True);w.video.setFocus()
    before=w.volume.value();QTest.keyClick(w.video,Qt.Key_Up);QTest.qWait(180)
    assert not panel.isVisible() and w.volume.value()==before+5
    QTest.keyClick(w.video,Qt.Key_Down);assert w.volume.value()==before
    checks['hidden_fullscreen_arrows_adjust_volume_without_opening_drawer']=True
    w.open_player_episodes();QTest.qWait(180)
    w.cinema.reveal_controls();QTest.qWait(30);w.position_player_episodes()
    assert panel.frameGeometry().top()>w.player_header.frameGeometry().bottom()
    assert panel.frameGeometry().bottom()<w.player_controls.frameGeometry().top()
    assert panel.height()<w.video.height()-100
    panel.grab().save(str(args.output/'fullscreen-six-episode-drawer.png'))
    checks['fullscreen_drawer_header_clear_of_top_and_bottom_controls']=True
    w.close_player_episodes();w.toggle_fullscreen();w.resize(1100,720);QTest.qWait(100)
    w.open_player_episodes();QTest.qWait(180)
    assert panel.frameGeometry().right()<=w.video.mapToGlobal(w.video.rect().bottomRight()).x()
    assert panel.height()<=w.video.height()-24,(panel.height(),w.video.height())
    w.close_player_episodes();checks['resized_drawer_remains_inside_video']=True
    for label,kind,forbidden in [('movie',1,False),('series',2,False),('forbidden_movie',1,True)]:
        detail_release=threading.Event()
        preview=dict(subjects[1],subjectType=kind,description='Known catalogue description shown before network completion.',genre='Drama',countryName='Fixture country')
        def deferred_detail(_):
            detail_release.wait(2)
            return {'subject':preview,'isSeries':kind==2,'isForbid':forbidden,'resource':{'seasons':[{'se':1,'maxEp':6}] if kind==2 else []}}
        try:
            with patch.object(w.api,'detail',side_effect=deferred_detail,create=True),patch.object(w,'_stream_future'):
                start=time.monotonic();w.open_detail(preview)
                assert w.description.text()==preview['description'] and w.detail_meta.text().startswith(str(preview['releaseDate'])[:4])
                assert not w.detail_cover.original.isNull() and not w.watch.isEnabled()
                assert w.season_row.isHidden() and w.episode_panel.isHidden()
                timings[label+'_known_detail_first_paint_ms']=round((time.monotonic()-start)*1000,2)
                detail_release.set();QTest.qWait(100)
                assert w.watch.isEnabled() is not forbidden
                assert w.season_row.isHidden() is (kind!=2)
                checks[label+'_preview_immediate_watch_and_seasons_wait_for_real_metadata']=True
        finally:detail_release.set()
    # Queue blocked image work through production dispatch. Metadata must not wait for it.
    release=threading.Event();entered=threading.Event();counter=[0];lock=threading.Lock()
    def blocked_image(_):
        with lock:
            counter[0]+=1
            if counter[0]>=4:entered.set()
        release.wait(3)
        from PySide6.QtGui import QImage
        return QImage()
    try:
        with patch.object(Artwork,'fetch_image',side_effect=blocked_image):
            for i in range(4):w.load_detail_art({'cover':{'url':'owned-image-'+str(i)}},w.request_generation)
            assert entered.wait(1)
            start=time.monotonic();future=w.submit(lambda:'metadata-ready',lambda _:None,message='')
            assert future.result(timeout=.5)=='metadata-ready'
            timings['metadata_while_four_images_blocked_ms']=round((time.monotonic()-start)*1000,2)
            checks['four_blocked_image_jobs_do_not_queue_metadata']=True
    finally:release.set()
    # Exercise the real delegate, not just crop arithmetic: all four inner
    # frame edges must contain image pixels for wide, near-portrait and square.
    for width,height in [(1600,900),(600,850),(600,600)]:
        key='owned-solid-'+str(width)+'-'+str(height)
        pixels=QPixmap(width,height);pixels.fill(QColor('#41b862'));w.art.images[key]=pixels
        w.catalog_model.replace([{'subjectId':key,'title':'Crop regression','cover':{'url':key}}])
        option=QStyleOptionViewItem();option.rect=QRect(0,0,184,316);option.font=w.grid.font()
        frame=w.poster_delegate.cover_rect(option.rect)
        source=w.poster_delegate.image_source_rect(width,height,frame.width(),frame.height())
        assert source.left()>=0 and source.top()>=0 and source.right()<=width+.001 and source.bottom()<=height+.001
        assert abs(source.width()/source.height()-frame.width()/frame.height())<.000001
        assert abs(source.width()-width)<.001 or abs(source.height()-height)<.001
        rendered=QImage(184,316,QImage.Format_ARGB32);rendered.fill(Qt.transparent)
        painter=QPainter(rendered);w.poster_delegate.paint(painter,option,w.catalog_model.index(0,0));painter.end()
        for x,y in [(frame.center().x(),frame.top()+4),(frame.center().x(),frame.bottom()-4),(frame.left()+4,frame.center().y()),(frame.right()-4,frame.center().y())]:
            assert rendered.pixelColor(round(x),round(y)).name()=='#41b862',(width,height,x,y,rendered.pixelColor(round(x),round(y)).name())
        checks[f'tile_{width}_{height}_proportional_crop_fills_all_edges']=True
    passed=True
finally:
    w.close();app.processEvents()
    (args.output/'result.json').write_text(json.dumps({'passed':passed,'checks':checks,'geometry':geometry,'timings':timings,'scope':'Actual native Qt controls, local captured same-title CDN bytes; no user data or live API/media.'},indent=2),encoding='utf-8')
print(json.dumps({'passed':True,'count':len(checks),'timings':timings}))
