"""Actual Qt click/fullscreen/menu/episode-end checks with local legal video."""
import json,os,time,faulthandler
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'verification/player-v090';OUT.mkdir(parents=True,exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR']=str(OUT/'user-data')
stack_log=(OUT/'stacks.txt').open('w',encoding='utf-8')
faulthandler.dump_traceback_later(15,repeat=True,file=stack_log)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
import main
from fluent_ui import stylesheet
class API:
    native=None;account_token='';last_play_info={}
    def __init__(self):self.calls=[];self.unavailable=None;self.bad_source=None
    def playback(self,subject,season=0,episode=0):
        self.calls.append((subject['subjectId'],season,episode))
        if self.unavailable==(season,episode):return []
        path=ROOT/'verification/sintel-1080p.mp4' if self.bad_source!=(season,episode) else OUT/'missing-video.mp4'
        return [{'url':QUrl.fromLocalFile(str(path)).toString(),'id':'fixture','resolutions':1080,'duration':52.2,'size':14000000}]
    def captions(self,*_,**kwargs):return {'captions':[]}
api=API();main.MovieBoxService=lambda:api;main.Window.load_home=lambda self:None
# This legal file fixture is local, so it bypasses the remote HTTP prebuffer bridge.
main.Window.maybe_prepare_media=lambda self,*args:None
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(stylesheet('eclipse'))
w=main.Window();w.update_timer.stop();w.resize(1440,940);w.show();checks={}
series={'subjectId':'series','subjectType':2,'title':'Fixture Series'}
movie={'subjectId':'movie','subjectType':1,'title':'Fixture Movie'}
def detail(subject):
    w.current=subject.copy();w.detail_loaded({'subject':subject,'isSeries':subject['subjectType']==2,'resource':{'seasons':[{'se':1,'maxEp':2},{'se':2,'maxEp':1}] if subject['subjectType']==2 else []}},w.request_generation)
def wait(predicate,seconds=10):
    print('Waiting at',w.playing_key,flush=True)
    deadline=time.monotonic()+seconds
    while not predicate() and time.monotonic()<deadline:QTest.qWait(40)
    assert predicate(),(w.status.text(),w.playing_key,w.stack.currentIndex())
try:
    detail(series);w.season.setCurrentIndex(0);w.episode.setCurrentIndex(0)
    w.watch_current();wait(lambda:w.frames>5 and w.player.isPlaying())
    QTest.mouseClick(w.video,Qt.LeftButton,pos=w.video.rect().center());assert w.player.playbackState()==QMediaPlayer.PausedState
    QTest.mouseClick(w.video,Qt.LeftButton,pos=w.video.rect().center());assert w.player.isPlaying()
    checks['single_video_click_pauses_and_resumes_immediately']=True
    QTest.mouseClick(w.video,Qt.LeftButton,pos=w.video.rect().center())
    QTest.mouseDClick(w.video,Qt.LeftButton,pos=w.video.rect().center());QTest.mouseRelease(w.video,Qt.LeftButton,pos=w.video.rect().center())
    assert w.cinema.isVisible() and w.cinema.isFullScreen() and w.player.isPlaying()
    w.toggle_fullscreen();checks['double_click_keeps_play_state_and_true_fullscreen']=True
    w.quality.showPopup();QTest.qWait(180)
    QTest.mouseClick(w.quality.view().viewport(),Qt.LeftButton,pos=w.quality.view().visualRect(w.quality.model().index(w.quality.currentIndex(),0)).center())
    assert w.player.isPlaying()
    checks['clicking_player_dropdown_does_not_toggle_video']=True
    controls=[w.pause,w.mute_button,w.clock,w.quality,w.caption_selector,w.audio_tracks,w.episode_browser_button,w.video_fit_button,w.fullscreen_button,w.subtitle_tools]
    assert max(x.geometry().center().y() for x in controls)-min(x.geometry().center().y() for x in controls)<=2
    assert all(x.geometry().right()<w.player_controls.width() for x in controls)
    w.player_controls.grab().save(str(OUT/'inline-controls.png'))
    checks['all_player_actions_share_one_row_below_timeline']=True
    assert not w.volume.isVisible()
    w.mute_button.setFocus();QTest.keyClick(w.mute_button,Qt.Key_Right)
    assert not w.volume.isVisible() and QApplication.focusWidget() is not w.volume
    w.mute_button.setFocus();QTest.keyClick(w.mute_button,Qt.Key_Return);QTest.qWait(180)
    assert w.volume_menu.isVisible() and w.volume.isVisible() and w.player.isPlaying()
    before=w.audio.volume();QTest.keyClick(w.volume,Qt.Key_Right);assert w.audio.volume()>before
    w.volume_menu.grab().save(str(OUT/'volume-popover.png'))
    QTest.keyClick(w.volume,Qt.Key_Return)
    assert not w.volume_menu.isVisible() and QApplication.focusWidget() is w.mute_button and w.player.isPlaying()
    checks['speaker_can_be_bypassed_and_slider_requires_explicit_activation']=True
    w.episode_browser_button.click();QTest.qWait(180)
    assert w.player_episode_panel.isVisible() and w.player.isPlaying()
    assert w.player_season_picker.width()<=180
    w.player_season_picker.setCurrentIndex(1)
    assert w.player.isPlaying() and w.playing_key.endswith(':1:1')
    assert w.player_episode_list.item(0).data(Qt.UserRole)==(2,1)
    w.player_episode_panel.grab().save(str(OUT/'desktop-episodes.png'))
    QTest.keyClick(w.player_season_picker,Qt.Key_Escape)
    assert not w.player_episode_panel.isVisible() and w.player.isPlaying()
    checks['in_player_seasons_browse_and_escape_without_pausing']=True
    w.toggle_fullscreen();QTest.qWait(250);w.cinema.reveal_controls();w.pause.setFocus()
    QTest.keyClick(w.pause,Qt.Key_Up)
    assert not w.player_episode_panel.isVisible() and w.player.isPlaying()
    checks['up_navigates_visible_controls_without_opening_episode_panel']=True
    w.subtitle_tools.click();QTest.qWait(100)
    assert w.subtitle_tools_menu.isVisible() and w.subtitle_delay.isVisible() and w.player.isPlaying(),(w.subtitle_tools_menu.isVisible(),w.subtitle_delay.isVisible(),w.player.playbackState())
    assert w.subtitle_delay.lineEdit().textMargins().left()>=10 and w.subtitle_tools_menu.width()<=320
    w.subtitle_tools_menu.grab().save(str(OUT/'player-more.png'))
    QTest.keyClick(w.subtitle_tools_menu,Qt.Key_Escape)
    assert w.cinema.isVisible() and w.player.isPlaying()
    checks['fullscreen_more_retains_download_and_subtitle_timing_without_pausing']=True
    w.cinema.hide_controls(force=True);w.video.setFocus()
    QTest.keyClick(w.video,Qt.Key_Up);QTest.qWait(180)
    assert w.player_episode_panel.parentWidget() is w.cinema and w.player_episode_panel.isVisible()
    assert w.player.isPlaying()
    checks['one_up_press_opens_right_panel_from_hidden_fullscreen_controls']=True
    w.player_season_picker.setCurrentIndex(1);w.player_episode_list.setFocus()
    QTest.keyClick(w.player_episode_list,Qt.Key_Return)
    wait(lambda:w.playing_key.endswith(':2:1') and w.player.isPlaying() and w.frames>2)
    assert w.cinema.isVisible() and not w.player_episode_panel.isVisible()
    checks['fullscreen_keyboard_episode_choice_plays_exact_season_and_episode']=True
    w.open_player_episodes();w.player_season_picker.setCurrentIndex(0)
    item=w.player_episode_list.item(0)
    QTest.mouseClick(w.player_episode_list.viewport(),Qt.LeftButton,pos=w.player_episode_list.visualItemRect(item).center())
    wait(lambda:w.playing_key.endswith(':1:1') and w.player.isPlaying() and w.frames>2)
    checks['mouse_episode_choice_does_not_pause_or_double_start']=True
    w.toggle_fullscreen()
    w.player.pause();w.stack.setCurrentIndex(1);w.season.showPopup();QTest.qWait(180)
    popup=w.season.view().window();assert popup.width()<=w.season.width()+4,(popup.size(),w.season.size())
    w.season.hidePopup();w.season.setFixedWidth(480);w.season.showPopup();QTest.qWait(180)
    assert w.season.view().window().width()<180
    w.season.view().window().grab().save(str(OUT/'content-sized-dropdown.png'))
    w.season.hidePopup();w.season.setFixedWidth(140);w.season.showPopup();QTest.qWait(180)
    popup=w.season.view().window()
    assert popup.windowOpacity()>.98
    popup.grab().save(str(OUT/'season-popup.png'));w.season.hidePopup()
    checks['season_popup_fits_control_width_and_fades_in']=True
    w.stack.setCurrentIndex(2);w.player.play();w.media_status(QMediaPlayer.EndOfMedia)
    wait(lambda:w.playing_key.endswith(':1:2') and w.player.isPlaying() and w.frames>2)
    assert not hasattr(w,'autoplay') and not hasattr(w,'next_episode')
    checks['series_automatically_starts_next_episode_without_checkbox']=True
    w.position_changed(w.player.duration()-1000);assert w.next_up_panel.isVisible()
    state=w.player.playbackState();w.dismiss_next_up();assert w.player.playbackState()==state
    checks['next_up_prompt_and_hide_do_not_pause_or_skip_story']=True
    w.media_status(QMediaPlayer.EndOfMedia);wait(lambda:w.playing_key.endswith(':2:1') and w.player.isPlaying() and w.frames>2)
    checks['last_episode_of_season_advances_to_next_season']=True
    w.media_status(QMediaPlayer.EndOfMedia);wait(lambda:w.stack.currentIndex()==1)
    assert w.player.playbackState()==QMediaPlayer.StoppedState
    checks['final_series_episode_returns_to_details']=True
    detail(movie);w.watch_current();wait(lambda:w.playing_key.startswith('movie:') and w.player.isPlaying() and w.player.position()>200)
    assert not w.episode_browser_button.isVisible()
    w.media_status(QMediaPlayer.EndOfMedia);assert w.stack.currentIndex()==1
    assert w.state['history']['movie:0:0']['completed'] is True
    checks['movie_end_returns_to_details_and_records_completion']=True
    w.stream_cache.clear();w.stream_requests.clear();api.unavailable=(1,2);detail(series);w.season.setCurrentIndex(0);w.episode.setCurrentIndex(0)
    w.watch_current();wait(lambda:w.playing_key.endswith(':1:1') and w.player.isPlaying() and w.frames>2)
    w.media_status(QMediaPlayer.EndOfMedia);wait(lambda:w.stack.currentIndex()==1)
    assert not w.player.isPlaying()
    checks['unavailable_next_source_returns_to_details']=True
    api.unavailable=None;api.bad_source=(1,2);w.stream_cache.clear();w.stream_requests.clear();detail(series);w.season.setCurrentIndex(0);w.episode.setCurrentIndex(0)
    w.watch_current();wait(lambda:w.playing_key.endswith(':1:1') and w.player.isPlaying() and w.frames>2)
    w.media_status(QMediaPlayer.EndOfMedia);wait(lambda:w.stack.currentIndex()==1)
    checks['native_decoder_failure_of_next_file_returns_to_details']=True
    checks['passed']=True
finally:
    print('Closing at',list(checks),flush=True)
    w.close();app.processEvents();(OUT/'result.json').write_text(json.dumps(checks,indent=2),encoding='utf-8');print(json.dumps(checks,indent=2));faulthandler.cancel_dump_traceback_later()
