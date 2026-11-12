"""Live acceptance for the reported GOT episode and season popup responsiveness."""
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).parent
OUT = ROOT / 'verification' / 'subtitle-fix-v031'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR'] = str(OUT / 'user-data')
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import Window
from fluent_ui import stylesheet

app = QApplication([])
app.setStyle('Fusion')
app.setStyleSheet(stylesheet(True))
w = Window()
w.audio.setMuted(True)
w.show()
checks = {}
gaps = []
last_tick = time.monotonic()

def tick():
    global last_tick
    now = time.monotonic()
    gaps.append((now-last_tick)*1000)
    last_tick = now

timer=QTimer()
timer.timeout.connect(tick)
timer.start(16)

def wait_for(predicate, timeout=40):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        app.processEvents()
        if predicate():return
        QTest.qWait(25)
    raise AssertionError(f'Timed out: {w.status.text()}, frames={w.frames}, position={w.player.position()}')

try:
    wait_for(lambda: bool(w.catalog_model.items))
    sample={'subjectId':'2036860087691609120','subjectType':2,'title':'Game of Thrones S1-S8'}
    key=sample['subjectId']+':8:6'
    w.state['history'][key]={'subject':sample,'position':3600000,'duration':4716000,'updated':time.time()}
    w.open_detail(sample)
    wait_for(lambda: bool(w.detail_data))
    assert (w.season.currentData() or {}).get('se')==8 and w.episode.currentData()==6
    wait_for(lambda: bool(w.prepared_media) and w.prepared_media['key']==key and not getattr(w,'prebuffering',False))
    w.watch_current()
    wait_for(lambda: w.frames>5 and bool(w.subtitle_track.cues))
    assert w.caption_selector.currentData()['lan']=='en'
    assert w.caption_selector.count()>=12
    checks['got_s8e6_languages']=[w.caption_selector.itemText(i) for i in range(1,w.caption_selector.count())]
    checks['got_s8e6_english_cues']=len(w.subtitle_track.cues)
    checks['automatic_english_selected']=True
    cue=w.subtitle_track.cues[0]
    w.seek_to(cue.start+200)
    wait_for(lambda: w.video.caption.text()==cue.text and w.video.caption.isVisible())
    wait_for(lambda: hasattr(w,'last_frame') and cue.start-1000 <= w.last_frame.startTime()/1000 <= cue.end+1000)
    w.player.pause()
    checks['timed_subtitle_visible']=True
    w.toggle_fullscreen()
    QTest.qWait(500)
    w.position_changed(cue.start+200)
    assert w.video.caption.isVisible()
    w.cinema.reveal_controls()
    QTest.qWait(300)
    w.cinema.screen().grabWindow(0).save(str(OUT/'got-subtitles-fullscreen.png'))
    w.toggle_fullscreen()
    w.leave_player()
    calls=[]
    original=w.api.playback
    def playback(*args,**kwargs):
        calls.append((args[1],args[2]))
        return original(*args,**kwargs)
    w.api.playback=playback
    w.season.showPopup()
    QTest.qWait(100)
    gaps.clear()
    last_tick=time.monotonic()
    for index in (0,1,2,3,4,5,6,7):
        w.season.setCurrentIndex(index)
        QTest.qWait(35)
    QTest.qWait(500)
    assert not calls, 'Playback lookup ran while the season popup was open'
    w.season.view().window().grab().save(str(OUT/'season-popup.png'))
    w.season.hidePopup()
    checks['no_preload_during_season_popup']=True
    assert w.season.view().sizeHintForRow(0)>=36
    checks['season_popup_row_height']=w.season.view().sizeHintForRow(0)
    recent=sorted(gaps[-60:])
    checks['selector_ui_p95_ms']=round(recent[int(len(recent)*.95)],1)
    checks['selector_ui_max_ms']=round(max(recent),1)
    assert checks['selector_ui_p95_ms']<65
    assert checks['selector_ui_max_ms']<100
    cached=w.subtitle_store.load(key,'en')
    assert cached and len(cached['cues'])==checks['got_s8e6_english_cues']
    checks['per_episode_subtitle_cache']=True
    result={'passed':True,'checks':checks}
except Exception as error:
    result={'passed':False,'checks':checks,'error':repr(error),'traceback':traceback.format_exc()}
finally:
    timer.stop()
    (OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    w.close()
    app.processEvents()
raise SystemExit(0 if result['passed'] else 1)
