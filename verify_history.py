"""Offline native-player close/relaunch regression. Supply your own local video."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--media',required=True,type=Path)
parser.add_argument('--output',type=Path,default=ROOT/'verification/history-v050')
parser.add_argument('--stage',choices=['play','reload'])
args=parser.parse_args()
output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
data=output/'fresh-user-data'
os.environ['MOVIEBOX_DATA_DIR']=str(data)
if not args.stage:
    for stage in ('play','reload'):
        subprocess.run([sys.executable,__file__,'--media',str(args.media.resolve()),'--output',str(output),'--stage',stage],check=True,timeout=55)
    print((output/'result.json').read_text())
    raise SystemExit

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
import main
from service import MovieBoxService
main.MovieBoxService=lambda:MovieBoxService(use_native=False)
main.Window.load_home=lambda self:None
app=QApplication([])
window=main.Window()
window.show();window.audio.setMuted(True)
subject={'subjectId':'history-fixture','subjectType':1,'title':'Local history regression'}
identity='history-fixture:0:0'
if args.stage=='play':
    assert not window.state['history'],'Use a fresh output directory for this regression.'
    window.state['saved']={'saved-one':{'subjectId':'saved-one','title':'Saved fixture one'},'saved-two':{'subjectId':'saved-two','title':'Saved fixture two'}}
    window.persist()
    window.current=subject;window.playing_subject=subject;window.playing_key=identity
    url=QUrl.fromLocalFile(str(args.media.resolve())).toString()
    window.current_stream={'url':url,'id':'fixture','duration':60,'resolutions':1080}
    window.start_video(url)
    deadline=time.monotonic()+25
    while time.monotonic()<deadline and (window.frames<5 or window.player.position()<1800):
        app.processEvents();QTest.qWait(25)
    assert window.frames>=5 and window.player.position()>=1800,'Native video did not begin'
    from release_updates import UpdateNotice
    window.update_notice=UpdateNotice('0.6.0','https://github.com/emransm877/moviebox-desktop/releases/tag/v0.6.0','https://github.com/emransm877/moviebox-desktop/releases/download/v0.6.0/MovieBox-Setup-0.6.0-windows-x64.exe','MovieBox-Setup-0.6.0-windows-x64.exe',1000)
    window.present_optional_update()
    assert not window.update_banner.isVisible(),'Updates must not interrupt the player'
    window.position_changed(window.player.position())
    checkpoint=window.player.position()
    # A media reset can reach position zero before window shutdown.
    window.player.stop()
    assert window.player.position()==0
    window.close();app.processEvents()
    restored=json.loads((data/'library.json').read_text())
    assert restored['history'][identity]['position']>=checkpoint-500
    assert (data/'library.json.bak').is_file()
else:
    assert identity in window.state['history'],'History did not survive a new process'
    window.show_history();app.processEvents()
    assert any(s['subjectId']=='history-fixture' for s in window.catalog_model.items)
    window.show_saved();app.processEvents()
    assert {s['subjectId'] for s in window.catalog_model.items}=={'saved-one','saved-two'}
    from release_updates import UpdateNotice
    window.update_notice=UpdateNotice('0.6.0','https://github.com/emransm877/moviebox-desktop/releases/tag/v0.6.0','https://github.com/emransm877/moviebox-desktop/releases/download/v0.6.0/MovieBox-Setup-0.6.0-windows-x64.exe','MovieBox-Setup-0.6.0-windows-x64.exe',1000)
    window.present_optional_update();assert window.update_banner.isVisible()
    window.skip_optional_update();assert not window.update_banner.isVisible()
    assert window.state['update_notifications']['skipped_version']=='0.6.0'
    window.configure_optional_updates(False)
    assert not window.state['update_notifications']['enabled']
    result={'fresh_data_native_playback':True,'position_zero_before_close_preserved':True,'new_process_history_loaded':True,'continue_watching_contains_title':True,'two_saved_titles_survive_new_process':True,'optional_update_deferred_during_playback':True,'optional_update_skip_and_opt_out':True,'position_ms':window.state['history'][identity]['position'],'scope':'Local video fixture, real Qt native player; no upstream API or production account data.'}
    (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    window.close();app.processEvents()
