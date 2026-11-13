"""Native Qt catalogue/navigation regression with an isolated fixture service."""
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'verification/catalogue-v060'
OUTPUT.mkdir(parents=True, exist_ok=True)
os.environ['MOVIEBOX_DATA_DIR'] = str(OUTPUT / 'user-data')

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main


class FixtureAPI:
    native = None
    account_token = ''

    def __init__(self):
        self.calls = []
        self.delay = 0

    def home(self):
        return {'operatingList': []}

    def request(self, path, body):
        self.calls.append((path, body.copy()))
        time.sleep(self.delay)
        kind, page = body['channelId'], body['page']
        return {'items': [{'subjectId': f'{kind}-{page}-{i}', 'subjectType': kind,
                          'title': f'Catalogue fixture {kind} / {page} / {i}',
                          'releaseDate': '2024-01-01', 'hasResource': False,
                          'cover': {'url': 'fixture://catalogue/cover'}} for i in range(3)],
                'pager': {'hasMore': page == 1, 'nextPage': str(page + 1)}}


api = FixtureAPI()
main.MovieBoxService = lambda: api
app = QApplication([])
app.setStyle('Fusion')
from fluent_ui import stylesheet
app.setStyleSheet(stylesheet(True))
window = main.Window()
cover = QPixmap(360, 540)
gradient = QLinearGradient(0, 0, 360, 540)
gradient.setColorAt(0, QColor('#143d48'))
gradient.setColorAt(1, QColor('#060c12'))
painter = QPainter(cover)
painter.fillRect(cover.rect(), gradient)
painter.end()
window.art.images['fixture://catalogue/cover'] = cover
window.state['update_notifications']['enabled'] = False
window.resize(1080, 640)
window.show()
checks = {}


def wait(predicate, timeout=5):
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(15)
    raise AssertionError('Timed out: ' + window.status.text())


try:
    window.nav_buttons['movies'].click()
    wait(lambda: len(window.catalog_model.items) == 3 and not window.jobs)
    assert window.heading.text() == 'Movies'
    assert api.calls[-1][1]['channelId'] == 1
    assert set(window.catalogue_filter_fields) == {'genre','year','country','classify','sort','rate'}
    assert window.catalogue_filter_panel.isVisible()
    checks['movie_channel_uses_live_catalogue_adapter'] = True

    delegate = window.poster_delegate
    cells = [window.grid.visualRect(window.catalog_model.index(row, 0)) for row in range(3)]
    window.grid.setFocus()
    window.grid.setCurrentIndex(window.catalog_model.index(0, 0))
    QTest.mouseMove(window.grid.viewport(), cells[0].center())
    QTest.qWait(190)
    app.processEvents()
    assert delegate.amounts.get(0, 0) > .98
    grown = delegate.cover_rect(cells[0], delegate.amounts[0])
    base = delegate.cover_rect(cells[0])
    assert grown.width() > base.width() and grown.height() > base.height()
    assert [window.grid.visualRect(window.catalog_model.index(row, 0)) for row in range(3)] == cells
    window.grab().save(str(OUTPUT / 'poster-focus-1080x640.png'))
    checks['poster_hover_grows_within_stable_cell_layout'] = True
    timings = []
    for index in range(30):
        started = time.perf_counter()
        QTest.keyClick(window.grid, Qt.Key_Right if index % 2 == 0 else Qt.Key_Left)
        app.processEvents()
        timings.append((time.perf_counter() - started) * 1000)
        QTest.qWait(16)
    QTest.qWait(190)
    app.processEvents()
    assert delegate.active_row == window.grid.currentIndex().row()
    assert delegate.metrics['maxActiveRows'] <= 2
    checks['keyboard_focus_takes_priority_over_stationary_pointer'] = True
    checks['poster_motion_is_bounded_to_two_transitioning_cells'] = True
    checks['poster_navigation_p95_ms'] = round(sorted(timings)[int(len(timings) * .95)], 2)
    checks['poster_navigation_max_ms'] = round(max(timings), 2)
    checks['poster_animation_frame_max_ms'] = round(delegate.metrics['maxFrameMs'], 2)

    for field, value in {'genre':'Action','year':'2024','country':'India',
                         'classify':'Hindi dub','sort':'Rating','rate':'8'}.items():
        picker = window.catalogue_filter_fields[field]
        index = picker.findData(value)
        assert index >= 0, (field, value)
        picker.setCurrentIndex(index)
    window.catalogue_apply.setFocus()
    QTest.keyClick(window.catalogue_apply, Qt.Key_Return)
    wait(lambda: not window.jobs and api.calls[-1][1].get('rate') == ['8','10'])
    assert all(api.calls[-1][1][field] == value for field, value in
               {'genre':'Action','year':'2024','country':'India','classify':'Hindi dub','sort':'Rating'}.items())
    checks['all_six_filters_sent_to_backend_by_keyboard_apply'] = True

    window.more.click()
    wait(lambda: len(window.catalog_model.items) == 6 and not window.jobs)
    assert api.calls[-1][1]['page'] == 2
    assert not window.more.isVisible()
    checks['pagination_appends_next_server_page_without_duplicates'] = True

    window.nav_buttons['series'].click()
    wait(lambda: not window.jobs and api.calls[-1][1]['channelId'] == 2)
    assert window.heading.text() == 'TV Shows'
    assert all(item['subjectType'] == 2 for item in window.catalog_model.items)
    assert window.catalogue_filter_fields['year'].currentData() == 'All'
    checks['tv_shows_have_separate_channel_and_filter_choices'] = True
    window.catalogue_filter_fields['year'].setCurrentIndex(window.catalogue_filter_fields['year'].findData('2024'))
    window.catalogue_apply.click()
    wait(lambda: not window.jobs and api.calls[-1][1].get('year') == '2024')
    window.catalogue_reset.click()
    wait(lambda: not window.jobs and 'year' not in api.calls[-1][1])
    checks['reset_removes_active_filters'] = True

    panel = window.catalogue_filter_panel
    for picker in window.catalogue_filter_fields.values():
        position = picker.mapTo(panel, picker.rect().topLeft())
        assert position.x() >= 0 and position.x() + picker.width() <= panel.width()
    assert window.grid.height() >= 100
    assert window.catalogue_apply.width() >= window.catalogue_apply.fontMetrics().horizontalAdvance('Apply filters') + 32
    window.grab().save(str(OUTPUT / 'filters-1080x640.png'))
    checks['six_filters_fit_1080x640_without_horizontal_clipping'] = True

    window.home_loaded({'operatingList': []})
    assert window.catalogue_kind == 'series' and window.heading.text() == 'TV Shows'
    checks['late_home_response_does_not_replace_selected_section'] = True

    api.delay = .15
    window.nav_buttons['movies'].click()
    window.show_saved()
    wait(lambda: not window.jobs)
    assert window.heading.text() == 'Your list' and not window.catalogue_filter_panel.isVisible()
    checks['stale_catalogue_response_does_not_replace_my_list'] = True
    assert window.state['catalogue_filters']['movies']['country'] == 'India'
    checks['filter_choices_remembered_independently_per_section'] = True
    checks['scope'] = 'Actual native Qt controls; fixture catalogue service, no upstream or production user data.'
    (OUTPUT / 'result.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    print(json.dumps(checks, indent=2))
finally:
    window.close()
    app.processEvents()
