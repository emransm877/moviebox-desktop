"""Actual Qt cache/selection regression with isolated data and a fixture service."""
import json,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'verification/cache-history-v080';OUT.mkdir(parents=True,exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR']=str(OUT/'user-data')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QItemSelectionModel
from PySide6.QtTest import QTest
import main
from catalogue_cache import CatalogueCache
from fluent_ui import stylesheet
class API:
    account_token='';native=None
    def __init__(self):self.calls=[];self.delay=0;self.variant=0
    def request(self,path,body):
        self.calls.append(body.copy());time.sleep(self.delay)
        kind,page=body['channelId'],body['page']
        items=[{'subjectId':f'{kind}-{page}-{i}','subjectType':kind,'title':f'Title {kind}/{page}/{i}'} for i in range(24)]
        if self.variant and page==1:items[0]={'subjectId':f'{kind}-new','subjectType':kind,'title':'New arrival'}
        return {'items':items,'pager':{'hasMore':page<2,'nextPage':page+1}}
api=API();main.MovieBoxService=lambda:api;main.Window.load_home=lambda self:None
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(stylesheet(True))
w=main.Window();w.catalogue_cache=CatalogueCache();w.update_timer.stop();w.resize(1080,700);w.show()
def wait():
    deadline=time.monotonic()+8
    while w.jobs and time.monotonic()<deadline:QTest.qWait(30)
    assert not w.jobs
checks={}
try:
    w.browse_catalogue('movies');wait();assert len(w.catalog_model.items)==24
    w.load_more();wait();assert len(w.catalog_model.items)==48
    w.grid.setCurrentIndex(w.catalog_model.index(20,0));w.grid.verticalScrollBar().setValue(220)
    w.browse_catalogue('series');wait();before=len(api.calls)
    w.browse_catalogue('movies');QTest.qWait(30)
    assert len(api.calls)==before and len(w.catalog_model.items)==48
    assert w.grid.currentIndex().row()==20 and w.grid.verticalScrollBar().value()>0
    checks['section_revisit_uses_cached_pages_selection_and_scroll_without_request']=True
    key=w.active_catalogue_cache_key;entry=w.catalogue_cache.get(key);entry['at']=time.time()-301;w.catalogue_cache.put(key,entry)
    w.browse_catalogue('series');api.delay=.15;w.browse_catalogue('movies')
    assert len(w.catalog_model.items)==48 and not w.empty.isVisible();wait()
    assert len(w.catalog_model.items)==48
    checks['stale_unchanged_refresh_keeps_visible_pages_and_position']=True
    entry=w.catalogue_cache.get(key);entry['at']=time.time()-301;w.catalogue_cache.put(key,entry)
    w.browse_catalogue('series');api.variant=1;w.browse_catalogue('movies');w.grid.setFocus();wait()
    assert w.catalog_model.items[0]['subjectId']!='1-new'
    assert w.catalogue_cache.get(key)['items'][0]['subjectId']=='1-new'
    w.catalogue_apply.click();wait();assert w.catalog_model.items[0]['subjectId']=='1-new'
    checks['new_results_wait_for_refresh_while_browsing_then_apply_without_blank']=True
    cache_path=OUT/'disk-cache.json';disk=CatalogueCache(cache_path);disk.put(key,w.catalogue_cache.get(key));disk.flush()
    assert CatalogueCache(cache_path).get(key)['items'][0]['subjectId']=='1-new'
    checks['catalogue_metadata_survives_disk_reload']=True
    movie={'subjectId':'movie','subjectType':1,'title':'Movie'};series={'subjectId':'show','subjectType':2,'title':'Series'}
    w.state['saved']={'movie':movie}
    w.state['history']={'movie:0:0':{'subject':movie,'position':1000,'duration':9000,'updated':3},'show:1:1':{'subject':series,'position':2000,'duration':9000,'updated':2},'show:1:2':{'subject':series,'position':3000,'duration':9000,'updated':1}}
    w.persist();w.show_history();w.begin_history_selection()
    w.grid.selectionModel().select(w.catalog_model.index(0,0),QItemSelectionModel.Select)
    w.playing_subject=movie;w.playing_key='movie:0:0';w.last_progress_checkpoint=('movie:0:0',1000,9000)
    w.history_remove.click();w.save_progress()
    assert 'movie:0:0' not in w.state['history'] and len(w.state['history'])==2 and 'movie' in w.state['saved']
    checks['single_remove_clears_continue_without_recreating_checkpoint_or_touching_my_list']=True
    w.history_undo_button.click();assert len(w.state['history'])==3
    w.begin_history_selection();w.history_all.click();assert len(w.grid.selectionModel().selectedRows())==2
    w.history_remove.click();assert not w.state['history'] and w.state['saved']=={'movie':movie}
    checks['select_all_removes_all_episode_records_for_selected_titles_only']=True
    w.history_undo_button.click();assert len(w.state['history'])==3
    w.begin_history_selection();w.history_all.click();w.history_all.click();assert not w.grid.selectionModel().selectedRows()
    w.finish_history_selection();w.persist();assert len(main.load_state()['history'])==3
    checks['undo_and_clear_selection_restore_persistent_history']=True
    checks['passed']=True
finally:
    w.close();app.processEvents()
    (OUT/'result.json').write_text(json.dumps(checks,indent=2),encoding='utf-8');print(json.dumps(checks,indent=2))
