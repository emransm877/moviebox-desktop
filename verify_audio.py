"""Live audio-language switch, runtime safety, subtitle replacement and resume."""
import json
import os
from pathlib import Path
import time
import traceback
ROOT=Path(__file__).parent
OUT=ROOT/'verification'/'audio-v040'
OUT.mkdir(parents=True,exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR']=str(OUT/'user-data')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import Window
from fluent_ui import stylesheet
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(stylesheet(True))
w=Window();w.audio.setMuted(True);w.show();checks={}
def wait_for(predicate,timeout=45):
    limit=time.monotonic()+timeout
    while time.monotonic()<limit:
        app.processEvents()
        if predicate():return
        QTest.qWait(25)
    raise AssertionError(f'Timed out: {w.status.text()}, position={w.player.position()}, pending={w.resume_position}')
try:
    wait_for(lambda:bool(w.catalog_model.items))
    subject={'subjectId':'2036860087691609120','subjectType':2,'title':'Game of Thrones S1-S8'}
    key=subject['subjectId']+':8:6'
    w.state['history'][key]={'subject':subject,'position':250000,'duration':4716000,'updated':time.time()}
    w.open_detail(subject);wait_for(lambda:bool(w.detail_data))
    wait_for(lambda:bool(w.prepared_media) and w.prepared_media['key']==key and not getattr(w,'prebuffering',False))
    w.watch_current();wait_for(lambda:w.frames>5 and bool(w.subtitle_track.cues))
    checks['audio_selector_visible']=w.audio_tracks.isVisible()
    choices=[w.audio_tracks.itemText(i) for i in range(w.audio_tracks.count())]
    checks['choices']=choices
    assert w.audio_tracks.isVisible() and any('Hindi' in s for s in choices)
    assert all(' sub' not in s.lower() for s in choices)
    w.player.pause();position=w.player.position()
    hindi=next(i for i in range(w.audio_tracks.count()) if ((w.audio_tracks.itemData(i) or {}).get('variant') or {}).get('lanCode')=='hi')
    w.audio_tracks.setCurrentIndex(hindi)
    wait_for(lambda:w.playing_subject['subjectId']=='5683555128238899472' and not w.resume_position and not w.player.isPlaying())
    wait_for(lambda:len(w.subtitle_track.cues)==613)
    assert abs(w.player.position()-position)<2000
    assert int(w.current_stream['resolutions'])==720
    assert all(int(s.get('duration') or 0)==4716 for s in w.streams)
    assert w.caption_selector.currentData()['lan']=='en'
    checks['hindi_position_preserved_ms']=w.player.position()
    checks['paused_state_preserved']=True
    checks['truncated_1080_excluded']=True
    checks['matching_hindi_quality']=w.current_stream['resolutions']
    checks['hindi_edition_english_cues']=len(w.subtitle_track.cues)
    checks['active_audio_label']=w.audio_tracks.currentText()
    w.grab().save(str(OUT/'hindi-audio.png'))
    w.audio_tracks.showPopup();QTest.qWait(150)
    w.audio_tracks.view().window().grab().save(str(OUT/'audio-languages.png'))
    w.audio_tracks.hidePopup()
    w.save_progress();assert key in w.state['history']
    assert w.state['audio_preferences'][subject['subjectId']]['subjectId']=='5683555128238899472'
    checks['language_preference_and_canonical_history_saved']=True
    w.leave_player();w.watch_current()
    wait_for(lambda:w.playing_subject['subjectId']=='5683555128238899472' and w.frames>5)
    checks['replay_keeps_audio_language']=True
    english=next(i for i in range(w.audio_tracks.count()) if ((w.audio_tracks.itemData(i) or {}).get('variant') or {}).get('subjectId')=='2036860087691609120')
    position=w.player.position();w.audio_tracks.setCurrentIndex(english)
    wait_for(lambda:w.playing_subject['subjectId']=='2036860087691609120' and not w.resume_position and w.frames>5)
    wait_for(lambda:len(w.subtitle_track.cues)==490)
    assert w.player.position()>=position-1500
    checks['switch_back_to_original_and_correct_subtitles']=True
    w.resize(1080,720);QTest.qWait(150)
    assert w.width()==1080
    assert w.audio_tracks.isVisible() and w.caption_selector.isVisible()
    checks['compact_audio_controls_fit']=True
    w.grab().save(str(OUT/'compact-audio-controls.png'))
    result={'passed':True,'checks':checks}
except Exception as error:
    result={'passed':False,'checks':checks,'error':repr(error),'traceback':traceback.format_exc()}
finally:
    (OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True);w.close();app.processEvents()
raise SystemExit(0 if result['passed'] else 1)
