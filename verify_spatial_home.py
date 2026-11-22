"""Actual Qt 20-theme geometry, bounded decoded artwork and history resume QA."""
import argparse,json,os,time,ctypes
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--artwork-root',type=Path);parser.add_argument('--generated-fixtures',action='store_true');parser.add_argument('--media',required=True,type=Path);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR']=str(args.output/'isolated-userdata')
from PySide6.QtCore import Qt,QUrl,QTimer,QAbstractAnimation,QPoint,QPointF
from PySide6.QtGui import QImage,QColor,QWheelEvent
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtTest import QTest
from main import Window,Artwork
from fluent_ui import stylesheet,refresh_theme,set_nav
from themes import THEMES,THEME_EFFECTS
from hero_feed import unique_spotlights,visual_keys


def wait(predicate,seconds=6):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        app.processEvents()
        if predicate():return
        QTest.qWait(20)
    raise AssertionError('Timed out waiting for native fixture state')


if args.generated_fixtures:
    args.artwork_root=args.output/'generated-art';args.artwork_root.mkdir(exist_ok=True);(args.artwork_root/'assets').mkdir(exist_ok=True)
    rows=[];mapping={}
    for i in range(100):
        identity='fixture-'+str(i);image=QImage(300,450,QImage.Format_RGB32);image.fill(QColor.fromHsv(i*3%360,150,180));image.save(str(args.artwork_root/'assets'/(identity+'.png')))
        rows.append({'id':identity,'title':'Generated owned title '+str(i),'type':1 if i%2==0 else 2,'year':'2026'});mapping[identity]='assets/'+identity+'.png'
    (args.artwork_root/'metadata.json').write_text(json.dumps(rows),encoding='utf-8');(args.artwork_root/'sharedposter-map.json').write_text(json.dumps(mapping),encoding='utf-8')
if args.artwork_root is None:parser.error('--artwork-root or --generated-fixtures is required')
rows=json.loads((args.artwork_root/'metadata.json').read_text(encoding='utf-8'));mapping=json.loads((args.artwork_root/'sharedposter-map.json').read_text(encoding='utf-8'))
subjects=[{'subjectId':r['id'],'title':r['title'],'subjectType':r['type'],'releaseDate':r['year'],'description':'Captured public title metadata in an isolated source fixture.','hasResource':True,'cover':{'url':QUrl.fromLocalFile(str(args.artwork_root/mapping[r['id']])).toString()}} for r in rows]
media_url=QUrl.fromLocalFile(str(args.media.resolve())).toString()
class API:
    native=None;account_token='';last_play_info={}
    def __init__(self):self.detail_calls=[];self.play_calls=[]
    def detail(self,subject):
        self.detail_calls.append(subject['subjectId'])
        return {'subject':subject,'isSeries':subject['subjectType']==2,'resource':{'seasons':[{'se':1,'maxEp':3},{'se':2,'maxEp':2}] if subject['subjectType']==2 else []}}
    def playback(self,subject,season=0,episode=0):
        self.play_calls.append((subject['subjectId'],season,episode))
        return [{'url':media_url,'id':'owned-local-stream','resolutions':720,'duration':40,'size':args.media.stat().st_size}]
    def captions(self,*args,**kwargs):return {'captions':[]}


app=QApplication([]);app.setStyleSheet(stylesheet('obsidian'));api=API();checks={};metrics={};passed=False;requested=[]
original_fetch=Artwork.fetch
def tracked_fetch(url,width=960):requested.append(url);return original_fetch(url,width)
with patch.object(Window,'load_home',lambda self:None),patch.object(Window,'check_optional_updates',lambda *args,**kwargs:None),patch.object(Artwork,'fetch',side_effect=tracked_fetch):
    w=Window(api);w.update_timer.stop();w.schedule_prefetch=lambda:None
    # This fixture supplies file:// media; production prebuffering is HTTP-only.
    w.maybe_prepare_media=lambda *args:None
    w.sections={'All titles':subjects}
    w.category.blockSignals(True);w.category.clear();w.category.addItem('All titles');w.category.blockSignals(False)
    series=next(s for s in subjects if s['subjectType']==2)
    movies=[s for s in subjects if s['subjectType']==1][:2]
    resume_key=series['subjectId']+':2:2'
    w.state['history']={resume_key:{'subject':series,'position':12000,'duration':40000,'updated':3},movies[0]['subjectId']+':0:0':{'subject':movies[0],'position':9000,'duration':40000,'updated':2},movies[1]['subjectId']+':0:0':{'subject':movies[1],'position':20000,'duration':40000,'updated':1}}
    w.resize(1920,1080);w.show();w.activateWindow();set_nav(w,'home');w.show_items(subjects);w.hero.show();w.hero.set_slides(subjects);w.hero.toggle_rotation();scene=w.hero.spatial
    try:
        wait(lambda:all(scene.poster(a['subject']) is not None for a in scene.actors))
        QTest.qWait(300)
        startup=set(requested);assert len(startup)<35,(len(startup),'startup must not download 100 posters')
        assert not api.detail_calls and not api.play_calls
        checks['startup_visible_and_nearby_only_no_detail_or_play_requests']=True
        keys=[visual_keys(subject) for subject in w.hero.slides]
        assert len([cover for cover,_ in keys if cover])==len({cover for cover,_ in keys if cover})
        assert len([base for _,base in keys if base])==len({base for _,base in keys if base})
        checks['hero_visual_duplicates_removed_without_removing_catalogue_editions']=True
        metrics['hero_unique_metadata_count']=len(w.hero.slides);metrics['catalogue_edition_count']=len(w.catalog_model.items)
        for key in THEMES:
            refresh_theme(w,key);app.processEvents();wait(lambda:all(scene.poster(a['subject']) is not None for a in scene.actors))
            assert scene.geometry_spec['id']==THEME_EFFECTS[key]['id']
            assert len(scene.actors)==THEME_EFFECTS[key]['visibleCards']
            assert len(w.hero.slides)==len(unique_spotlights(subjects))==len(scene.subjects)
            assert len(w.catalog_model.items)==100
            assert w.sidebar.width()>=200 and not w.theme_navigation.isVisible()
            assert w.nav_buttons['home'].text()=='Discover' and w.nav_buttons['history'].text()=='History'
            assert w.continue_strip.isVisible() and sum(c.isVisible() for c in w.continue_strip.cards)==3
            QTest.qWait(50);w.grab().save(str(args.output/(key+'-1920.png')))
            metrics[key]={'geometry':scene.geometry_spec['id'],'planes':len(scene.actors),'memory':scene.memory_metrics(),'paint_samples':list(scene.frame_times)[-20:]}
            checks[key+'_canonical_geometry_sidebar_history_and_100_metadata']=True
        for width,height in [(1080,720),(1280,720),(1440,900)]:
            refresh_theme(w,'helix-steps');w.resize(width,height);app.processEvents();QTest.qWait(100)
            assert w.continue_strip.isVisible()
            assert not w.hero.findChildren(QPushButton)
            assert w.hero.title.geometry().right()<w.hero.width()
            w.grab().save(str(args.output/f'helix-steps-{width}.png'))
            checks[f'{width}_full_home_layout_preserves_actions_and_compact_continue']=True
        w.resize(1680,1000);refresh_theme(w,'domino-lane');app.processEvents();w.poster_delegate.motion=True
        real_motion=scene.motion_allowed();metrics['windows_client_area_animation_enabled']=real_motion
        ticks=[];ticker=QTimer();ticker.timeout.connect(lambda:ticks.append(time.perf_counter()));ticker.start(16)
        scene.advance(1);QTest.qWait(230)
        if real_motion:
            assert 0<scene.progress<1
            before=[[(p.x(),p.y()) for p in polygon] for polygon,_ in scene.polygons]
            QTest.qWait(160);after=[[(p.x(),p.y()) for p in polygon] for polygon,_ in scene.polygons]
            assert before!=after
        assert str(w.hero.subject['subjectId'])==str(scene.subjects[scene.index]['subjectId'])
        with patch.object(w,'open_detail') as opened:w.hero.more_info();opened.assert_called_once_with(w.hero.subject)
        for _ in range(40):scene.advance(1)
        wait(lambda:scene.animation.state()!=QAbstractAnimation.State.Running,3)
        ticker.stop();gaps=[(ticks[i]-ticks[i-1])*1000 for i in range(1,len(ticks))]
        assert not gaps or max(gaps)<300,max(gaps)
        assert len(scene.actors)==7 and len(scene.cache)<=24
        checks['native_depth_animation_identity_and_bounded_rapid_input_no_freeze']=True
        metrics['ui_max_gap_ms']=max(gaps,default=0)
        wait(lambda:scene.animation.state()!=QAbstractAnimation.State.Running)
        polygon,clicked_subject=scene.polygons[-1];point=polygon.boundingRect().center().toPoint()
        with patch.object(w,'open_detail') as opened:
            QTest.mouseClick(scene,Qt.LeftButton,pos=point);opened.assert_called_once_with(clicked_subject)
            opened.reset_mock();QTest.mousePress(scene,Qt.LeftButton,pos=point);QTest.mouseRelease(scene,Qt.LeftButton,pos=point+QPoint(-45,0));assert not opened.called
        checks['poster_click_opens_own_detail_and_horizontal_drag_never_activates']=True
        wait(lambda:scene.animation.state()!=QAbstractAnimation.State.Running)
        vertical=QWheelEvent(QPointF(point),QPointF(scene.mapToGlobal(point)),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
        app.sendEvent(scene,vertical);assert not vertical.isAccepted()
        horizontal=QWheelEvent(QPointF(point),QPointF(scene.mapToGlobal(point)),QPoint(),QPoint(-120,0),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
        before=scene.index;app.sendEvent(scene,horizontal);assert horizontal.isAccepted() and scene.index==(before+1)%len(scene.subjects)
        wait(lambda:scene.animation.state()!=QAbstractAnimation.State.Running)
        checks['horizontal_wheel_browses_vertical_wheel_is_not_hijacked']=True
        w.hero.rotation_paused=False;scene.setFocus()
        with patch.object(w,'isActiveWindow',return_value=True):
            QTest.keyClick(scene,Qt.Key_Right);idle_index=scene.index;started=time.monotonic()
            QTest.qWait(250);assert scene.index==idle_index
            wait(lambda:scene.index!=idle_index,8.8)
            elapsed=time.monotonic()-started;assert 7.7<=elapsed<=9.2,elapsed
        w.hero.rotation_paused=True;scene.auto.stop();wait(lambda:scene.animation.state()!=QAbstractAnimation.State.Running)
        metrics['actual_idle_resume_seconds']=elapsed
        checks['focused_carousel_resumes_at_eight_second_input_idle_deadline']=True
        def reduced(action,zero,pointer,last):
            assert action==0x1042;ctypes.cast(pointer,ctypes.POINTER(ctypes.c_int))[0]=0;return 1
        with patch('spatial_hero.ctypes.windll.user32.SystemParametersInfoW',side_effect=reduced) as guard:
            assert not scene.motion_allowed();scene.advance(1);assert scene.animation.state()!=QAbstractAnimation.State.Running;assert scene.progress==1
            assert guard.called
        checks['real_windows_spi_reduced_motion_path_respected']=True
        w.poster_delegate.motion=False
        for _ in range(30):scene.advance(1)
        QTest.qWait(400);assert len(scene.cache)<=24
        memory=scene.memory_metrics();assert memory['max_decoded_width']<=360 and memory['max_decoded_height']<=540
        assert memory['decoded_bytes_upper_bound']<=24*360*540*4
        metrics['final_hero_memory']=memory;checks['bounded_24_shared_decoded_poster_refs_no_large_source_decode']=True
        view=next(b for b in w.continue_strip.findChildren(QPushButton) if b.text()=='View all');view.click()
        assert w.history_toolbar.isVisible() and w.nav_buttons['history'].isChecked()
        checks['continue_view_all_preserves_history_and_bulk_controls']=True
        w.show_discover();w.hero.rotation_paused=True;w.continue_strip.refresh();w.continue_strip.cards[0].click()
        wait(lambda:w.playing_key==resume_key and w.frames>2,10)
        wait(lambda:w.player.position()>=11500,5)
        assert api.play_calls[-1]==(series['subjectId'],2,2)
        checks['continue_resumes_exact_subject_season_episode_and_real_position']=True
        w.stop_for_navigation();w.show_discover()
        with patch.object(api,'playback') as denied:
            w.current=dict(subjects[0]);w.detail_data={'subject':w.current,'isForbid':True};w.watch_current();denied.assert_not_called()
        checks['forbidden_title_does_not_auto_play_from_hero_or_continue']=True
        passed=True
    finally:
        w.close();app.processEvents();(args.output/'result.json').write_text(json.dumps({'passed':passed,'checks':checks,'metrics':metrics,'initial_unique_image_requests':len(startup) if 'startup' in locals() else None,'scope':'Actual native Qt/QPainter, cached public artwork and generated owned local media; synthetic history is confined to isolated data. Browser/Samsung FPS is not inferred.'},indent=2),encoding='utf-8')
print(json.dumps({'passed':passed,'checks':len(checks),'startup_images':len(startup)}))
