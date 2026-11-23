"""Keep the computer/display awake only while the visible player is playing."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

import power
from power import KeepAwake, ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED

ROOT = Path(__file__).resolve().parent
PLAYING = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED


class Recorder:
    def __init__(self, result=ES_CONTINUOUS):
        self.calls, self.result = [], result

    def __call__(self, flags):
        self.calls.append(flags)
        return self.result


class KeepAwakeFlags(unittest.TestCase):
    def test_flag_values_match_win32(self):
        self.assertEqual(ES_CONTINUOUS, 0x80000000)
        self.assertEqual(ES_SYSTEM_REQUIRED, 0x1)
        self.assertEqual(ES_DISPLAY_REQUIRED, 0x2)
        self.assertEqual(power.PLAYBACK_FLAGS, 0x80000003)

    def test_play_pause_stop_transitions(self):
        setter = Recorder()
        keep = KeepAwake(setter)
        keep.set_active(True)
        self.assertEqual(setter.calls, [PLAYING])
        self.assertTrue(keep.active)
        keep.set_active(False)  # pause
        self.assertEqual(setter.calls, [PLAYING, ES_CONTINUOUS])
        keep.set_active(True)  # resume
        keep.release()  # stop / close / quit
        self.assertEqual(setter.calls, [PLAYING, ES_CONTINUOUS, PLAYING, ES_CONTINUOUS])
        self.assertFalse(keep.active)

    def test_repeated_calls_are_idempotent(self):
        setter = Recorder()
        keep = KeepAwake(setter)
        for _ in range(5):
            keep.set_active(True)
        for _ in range(5):
            keep.set_active(False)
            keep.release()
        self.assertEqual(setter.calls, [PLAYING, ES_CONTINUOUS])

    def test_release_without_activation_makes_no_call(self):
        setter = Recorder()
        KeepAwake(setter).release()
        self.assertEqual(setter.calls, [])

    def test_failed_call_is_retried_and_never_raises(self):
        setter = Recorder(result=0)
        keep = KeepAwake(setter)
        keep.set_active(True)
        self.assertFalse(keep.active)
        setter.result = ES_CONTINUOUS
        keep.set_active(True)
        self.assertTrue(keep.active)
        self.assertEqual(setter.calls, [PLAYING, PLAYING])

        def broken(flags):
            raise OSError('unavailable')
        keep = KeepAwake(broken)
        keep.set_active(True)
        keep.release()
        self.assertFalse(keep.active)

    def test_request_stays_on_the_thread_that_made_it(self):
        setter = Recorder()
        keep = KeepAwake(setter)
        keep.set_active(True)
        worker = threading.Thread(target=keep.release)
        worker.start()
        worker.join()
        self.assertTrue(keep.active)
        self.assertEqual(setter.calls, [PLAYING])
        keep.release()
        self.assertEqual(setter.calls, [PLAYING, ES_CONTINUOUS])

    def test_windows_uses_kernel32_set_thread_execution_state(self):
        fake_ctypes = MagicMock()
        function = fake_ctypes.windll.kernel32.SetThreadExecutionState
        function.return_value = ES_CONTINUOUS
        with patch.object(power.os, 'name', 'nt'), patch.dict(sys.modules, {'ctypes': fake_ctypes}):
            keep = KeepAwake()
            keep.set_active(True)
            keep.set_active(True)
            keep.set_active(False)
        self.assertEqual([call.args[0] for call in function.call_args_list], [PLAYING, ES_CONTINUOUS])

    def test_other_platforms_are_noop(self):
        fake_ctypes = MagicMock()
        with patch.object(power.os, 'name', 'posix'), patch.dict(sys.modules, {'ctypes': fake_ctypes}):
            keep = KeepAwake()
            keep.set_active(True)
            keep.release()
        fake_ctypes.windll.kernel32.SetThreadExecutionState.assert_not_called()

    def test_missing_kernel32_is_noop(self):
        fake_ctypes = MagicMock()
        type(fake_ctypes).windll = property(lambda self: (_ for _ in ()).throw(AttributeError('windll')))
        with patch.object(power.os, 'name', 'nt'), patch.dict(sys.modules, {'ctypes': fake_ctypes}):
            keep = KeepAwake()
            keep.set_active(True)
            keep.release()
        self.assertFalse(keep.active)


class WindowKeepAwakeHooks(unittest.TestCase):
    def test_actual_qt_window_hooks(self):
        # Separate process guarantees app userdata is isolated before importing main.
        code = r'''
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtCore import QTimer
import main
from power import KeepAwake
from smoke import OfflineMediaService
from fluent_ui import stylesheet
app=QApplication([])
app.setStyleSheet(stylesheet('eclipse'))
main.Window.load_home=lambda self:None
main.Window.check_optional_updates=lambda *a,**kw:None
w=main.Window(api=OfflineMediaService())
calls=[]
def setter(flags):
    calls.append(flags);return 0x80000000
w.keep_awake=KeepAwake(setter)
state=[QMediaPlayer.StoppedState]
PLAY,CLEAR=0x80000003,0x80000000
with patch.object(main.QMediaPlayer,'playbackState',lambda self:state[0]):
    def go(new):
        state[0]=new;w.player.playbackStateChanged.emit(new);app.processEvents()
    w.stack.setCurrentIndex(2)
    go(QMediaPlayer.PlayingState); assert w.keep_awake.active and calls==[PLAY],calls
    go(QMediaPlayer.PlayingState); assert calls==[PLAY],calls
    go(QMediaPlayer.PausedState); assert not w.keep_awake.active and calls[-1]==CLEAR,calls
    go(QMediaPlayer.PlayingState); assert w.keep_awake.active
    w.player.mediaStatusChanged.emit(QMediaPlayer.BufferingMedia); assert w.keep_awake.active,'short buffering keeps awake'
    w.keep_awake_stall_timer.setInterval(40)
    w.player.mediaStatusChanged.emit(QMediaPlayer.StalledMedia); QTest.qWait(150)
    assert not w.keep_awake.active,'long stall releases'
    w.player.mediaStatusChanged.emit(QMediaPlayer.BufferedMedia); assert w.keep_awake.active,'recovered stream re-acquires'
    go(QMediaPlayer.StoppedState); assert not w.keep_awake.active,'stop/end of media releases'
    go(QMediaPlayer.PlayingState); assert w.keep_awake.active
    w.stack.setCurrentIndex(0); assert not w.keep_awake.active,'navigation away releases'
    w.stack.setCurrentIndex(2); assert w.keep_awake.active
    w.prebuffering=True; w.update_keep_awake(); assert not w.keep_awake.active,'muted detail prebuffer never keeps awake'
    w.prebuffering=False; w.update_keep_awake(); assert w.keep_awake.active
    n=len(calls); QTimer.singleShot(0,app.quit); app.exec()
    assert not w.keep_awake.active and calls[n:]==[CLEAR],'app quit releases'
    go(QMediaPlayer.PlayingState); assert w.keep_awake.active
    w.close(); app.processEvents()
    assert not w.keep_awake.active and calls[-1]==CLEAR,'window close releases'
    go(QMediaPlayer.PlayingState); assert not w.keep_awake.active,'closing window never re-acquires'
print('PASS keep-awake window hooks',len(calls))
'''
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, MOVIEBOX_DATA_DIR=folder, QT_QPA_PLATFORM='offscreen')
            result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS keep-awake window hooks', result.stdout)


if __name__ == '__main__':
    unittest.main()
