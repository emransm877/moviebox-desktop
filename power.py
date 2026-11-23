"""Keep the computer and display awake while media is actually playing.

Windows' SetThreadExecutionState is a per-thread request: the flags belong to
the calling thread and are dropped when that thread exits. MovieBox therefore
calls it only from the Qt GUI thread, and only when the requested state
changes. Other platforms are a no-op here; the macOS build has its own
implementation with the same KeepAwake API.
"""
from __future__ import annotations
import os
import threading

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
PLAYBACK_FLAGS = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED


def _windows_setter():
    if os.name != 'nt':
        return None
    try:
        import ctypes
        function = ctypes.windll.kernel32.SetThreadExecutionState
        function.argtypes = [ctypes.c_uint32]
        function.restype = ctypes.c_uint32
        return function
    except (AttributeError, OSError, ImportError):
        return None


class KeepAwake:
    """Idempotent sleep/display-idle inhibitor. It never raises into the UI."""

    def __init__(self, setter=None):
        self._setter = setter if setter is not None else _windows_setter()
        self._thread = None
        self.active = False

    def set_active(self, active: bool) -> None:
        active = bool(active)
        if active == self.active:
            return
        if self._thread is not None and self._thread != threading.get_ident():
            # The previous request belongs to another thread and cannot be
            # cleared from here; never move the request between threads.
            return
        if self._apply(PLAYBACK_FLAGS if active else ES_CONTINUOUS):
            self.active = active
            self._thread = threading.get_ident() if active else None

    def release(self) -> None:
        self.set_active(False)

    def _apply(self, flags):
        if self._setter is None:
            return True
        try:
            # A zero result means the call failed; keep the previous state so a
            # later transition can retry.
            return bool(self._setter(flags))
        except Exception:
            return False
