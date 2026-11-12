"""Native QR login using MovieBox's own confirmation flow."""
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
import qrcode


class LoginDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.ticket = ''
        self.remote_status = 'WAITING'
        self.busy = False
        self.started = time.monotonic()
        self.setWindowTitle('Sign in to MovieBox')
        self.setFixedSize(430, 530)
        layout = QVBoxLayout(self)
        heading = QLabel('Sign in to MovieBox')
        heading.setObjectName('heading')
        layout.addWidget(heading)
        self.qr = QLabel('Creating a login code…')
        self.qr.setStyleSheet('background:white;color:#182431;border-radius:15px;padding:5px')
        self.qr.setFixedSize(360, 310)
        self.qr.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.qr, 0, Qt.AlignCenter)
        instructions = QLabel('In MovieBox on your phone, open Me and tap the scan icon. Scan this code, then confirm the login on your phone.')
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.status = QLabel('Waiting…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        close = QPushButton('Cancel')
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)
        window.submit(lambda: window.api.request('/user/qr-login-create', {}), self.created,
                      message='', failure=self.error)
        from fluent_ui import apply_window_material
        from PySide6.QtWidgets import QApplication
        QTimer.singleShot(0, lambda: apply_window_material(self, bool(QApplication.instance().property('movieboxDark'))))

    def created(self, data):
        if not self.isVisible():
            return
        self.ticket = data.get('ticket') or ''
        content = data.get('qrUrl') or self.ticket
        if not self.ticket or not content:
            self.error('MovieBox did not return a login code.')
            return
        code = qrcode.QRCode(border=4, box_size=6)
        code.add_data(content)
        code.make(fit=True)
        matrix = code.get_matrix()
        size = len(matrix)
        image = QImage(size * 6, size * 6, QImage.Format_RGB32)
        image.fill(QColor('white'))
        painter = QPainter(image)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('black'))
        for row, cells in enumerate(matrix):
            for column, filled in enumerate(cells):
                if filled:
                    painter.drawRect(column * 6, row * 6, 6, 6)
        painter.end()
        self.qr.setPixmap(QPixmap.fromImage(image).scaled(300, 300, Qt.KeepAspectRatio, Qt.FastTransformation))
        self.status.setText('Scan and confirm on your phone.')

    def poll(self):
        if not self.isVisible() or not self.ticket or self.busy:
            return
        if time.monotonic() - self.started > 180:
            self.error('This login code expired. Close this window and try again.')
            return
        self.busy = True
        self.window.submit(lambda: self.window.api.request('/user/qr-login-poll',
            {'ticket': self.ticket, 'lastStatus': self.remote_status}), self.polled,
            message='', failure=self.error)

    def polled(self, data):
        self.busy = False
        if not self.isVisible():
            return
        self.remote_status = data.get('status', 'WAITING')
        if self.remote_status == 'SCANNED':
            self.status.setText('Scanned. Confirm the login on your phone.')
        elif self.remote_status == 'CONFIRMED':
            self.timer.stop()
            self.window.submit(lambda: self.window.api.request('/user/qr-login-fetch', {'ticket': self.ticket}),
                               self.confirmed, message='', failure=self.error)
        elif self.remote_status in ('EXPIRED', 'CANCELED', 'CONSUMED'):
            self.error('Login code expired or was cancelled. Please try again.')

    def confirmed(self, data):
        if not self.isVisible():
            return
        token = data.get('token')
        if isinstance(token, dict):
            token = token.get('token')
        if not isinstance(token, str) or not token:
            self.error('MovieBox did not complete the login.')
            return
        self.window.store_account(token)
        self.accept()

    def error(self, message):
        self.busy = False
        self.timer.stop()
        self.status.setText(message)

    def done(self, result):
        self.timer.stop()
        super().done(result)
