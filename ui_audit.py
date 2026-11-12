"""Capture native design states and check the compact Windows layout."""
from pathlib import Path
import json
import sys
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from main import Window, load_state
from fluent_ui import stylesheet, refresh_theme, open_settings
from account import LoginDialog


app = QApplication([])
app.setStyle('Fusion')
app.setStyleSheet(stylesheet(True))
window = Window()
window.show()
output = Path('verification/fluent-ui-audit')
output.mkdir(parents=True, exist_ok=True)
result = {'checks': {}, 'screenshots': []}
step = 'home'
started = time.monotonic()
ready_at = None


def capture(name):
    window.grab().save(str(output / (name + '.png')))
    result['screenshots'].append(name)


def tick():
    global step, ready_at
    if time.monotonic() - started > 60:
        finish(False)
        return
    if step == 'home' and window.sections and not window.hero.image.isNull():
        if ready_at is None:
            ready_at = time.monotonic()
            return
        if time.monotonic() - ready_at < 1:
            return
        capture('home-dark')
        window.resize(1080, 720)
        step = 'compact'
    elif step == 'compact':
        result['checks']['compact_size'] = [window.width(), window.height()]
        result['checks']['compact_layout_fits'] = window.width() == 1080 and window.height() == 720
        capture('home-compact')
        sample = window.catalog_model.items[0]
        window.open_detail(sample)
        step = 'detail'
    elif step == 'detail' and window.detail_data:
        capture('detail-compact')
        result['checks']['detail_scroll_ready'] = hasattr(window.stack.widget(1), 'verticalScrollBar')
        window.show_downloads()
        step = 'downloads'
    elif step == 'downloads':
        capture('downloads')
        result['checks']['downloads_empty_state'] = window.download_empty.isVisible() if not window.download_list.count() else True
        window.show_saved()
        step = 'saved'
    elif step == 'saved':
        capture('my-list')
        window.show_discover()
        window.resize(1440, 940)
        refresh_theme(window, False)
        step = 'light'
    elif step == 'light':
        capture('home-light')
        refresh_theme(window, True)
        def dialog_capture():
            dialog = QApplication.activeModalWidget()
            if dialog:
                dialog.grab().save(str(output / 'settings.png'))
                dialog.reject()
        step = 'account'
        QTimer.singleShot(250, dialog_capture)
        open_settings(window)
        window.login_dialog = LoginDialog(window)
        window.login_dialog.show()
    elif step == 'account' and window.login_dialog.qr.pixmap() and not window.login_dialog.qr.pixmap().isNull():
        window.login_dialog.grab().save(str(output / 'account.png'))
        result['checks']['native_qr_rendered'] = True
        window.login_dialog.reject()
        finish(True)


def finish(passed):
    timer.stop()
    result['passed'] = passed and result['checks'].get('compact_layout_fits', False)
    result['elapsed_seconds'] = round(time.monotonic() - started, 2)
    (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    window.close()
    app.exit(0 if result['passed'] else 1)


timer = QTimer()
timer.timeout.connect(tick)
timer.start(300)
sys.exit(app.exec())
