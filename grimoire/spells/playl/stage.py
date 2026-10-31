# SPDX-License-Identifier: GPL-3.0-or-later
"""The stage: the video (or the song's grayscale cover, or the "open something" screen) with the controls floating
over its foot. Over a playing video the controls and the pointer hide after a moment without mouse movement.
The page moves the whole stage into a window of its own for fullscreen and back."""
from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QToolButton,
                               QVBoxLayout, QWidget)

from grimoire.glyphs import _pixmap, glyph
from grimoire.i18n import ltr, tr
from grimoire.spells.playl.media import clock
from grimoire.spells.playl.seekbar import Bubble, SeekBar
from grimoire.spells.playl.video import VideoView

HIDE_AFTER_MS = 2500
CONTROLS_QSS = """
QWidget#PlayControls QToolButton { border: none; border-radius: 8px; padding: 6px; background: transparent;
                                   color: #e8e8e8; }
QWidget#PlayControls QToolButton:hover { background: rgba(255, 255, 255, 22); }
QWidget#PlayControls QToolButton:checked { background: rgba(255, 255, 255, 34); }
QWidget#PlayControls QToolButton:disabled { color: #4a4a4a; }
QWidget#PlayControls QToolButton::menu-indicator { image: none; width: 0; }
QWidget#PlayControls QToolButton#Speed { font-family: "IBM Plex Mono"; font-size: 12px; padding: 6px 8px; }
QWidget#PlayControls QLabel#Time { font-family: "IBM Plex Mono"; font-size: 11px; color: #bdbdbd; }
QWidget#PlayControls QLabel#NowTitle { color: #ffffff; font-weight: 600; }
QWidget#PlayControls QLabel#NowSub { color: #8c8c8c; }
QFrame#Chip { background: rgba(10, 10, 10, 230); border: 1px solid #333333; border-radius: 10px; }
QFrame#Chip QPushButton { padding: 4px 10px; }
"""


def tool(icon: str, tip: str, size: int = 20, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setIcon(glyph(icon, size))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)          # space and the arrows belong to the player, not a button
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class Controls(QWidget):
    """Seek bar + transport + the per-file menus + volume, on a dark fade."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlayControls")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 28, 14, 10)
        lay.setSpacing(2)
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.cur = QLabel("0:00")
        self.cur.setObjectName("Time")
        self.total = QLabel("0:00")
        self.total.setObjectName("Time")
        self.bar = SeekBar()
        row1.addWidget(self.cur)
        row1.addWidget(self.bar, 1)
        row1.addWidget(self.total)
        self.timeline = QWidget()
        self.timeline.setLayoutDirection(Qt.LayoutDirection.LeftToRight)   # time runs left to right
        self.timeline.setLayout(row1)
        row1.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.timeline)

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        self.prev = tool("prev", tr("grimoire.spells.playl.stage", "Previous (P)"))
        self.play = tool("play", tr("grimoire.spells.playl.stage", "Play (Space)"), 26)
        self.next = tool("next", tr("grimoire.spells.playl.stage", "Next (N)"))
        for b in (self.prev, self.play, self.next):
            row2.addWidget(b)
        row2.addSpacing(8)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.title = QLabel()
        self.title.setObjectName("NowTitle")
        self.sub = QLabel()
        self.sub.setObjectName("NowSub")
        for lab in (self.title, self.sub):
            lab.setTextFormat(Qt.TextFormat.PlainText)
            lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            texts.addWidget(lab)
        row2.addLayout(texts, 1)
        self.speed = QToolButton()
        self.speed.setObjectName("Speed")
        self.speed.setText("1×")
        self.speed.setToolTip(tr("grimoire.spells.playl.stage", "Speed ([ and ])"))
        self.speed.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.audio = tool("music", tr("grimoire.spells.playl.stage", "Audio track"))
        self.audio.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.subs = tool("subtitles", tr("grimoire.spells.playl.stage", "Subtitles"))
        self.subs.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.repeat = tool("repeat", tr("grimoire.spells.playl.stage", "Repeat"))
        self.shuffle = tool("shuffle", tr("grimoire.spells.playl.stage", "Shuffle"), checkable=True)
        for b in (self.speed, self.audio, self.subs, self.repeat, self.shuffle):
            row2.addWidget(b)
        row2.addSpacing(6)
        self.mute = tool("audio", tr("grimoire.spells.playl.stage", "Mute (M)"), checkable=True)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.setFixedWidth(96)
        self.volume.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        row2.addWidget(self.mute)
        row2.addWidget(self.volume)
        row2.addSpacing(6)
        self.queue = tool("queue", tr("grimoire.spells.playl.stage", "Queue (Q)"), checkable=True)
        self.full = tool("fullscreen", tr("grimoire.spells.playl.stage", "Fullscreen (F)"))
        row2.addWidget(self.queue)
        row2.addWidget(self.full)
        lay.addLayout(row2)
        self.setStyleSheet(CONTROLS_QSS)

    def resizeEvent(self, e):
        self._fit(e.size().width())
        super().resizeEvent(e)

    def _fit(self, width: int):
        """Too narrow for every control (the queue open in a small window): leave out the least needed ones, the
        volume slider first (mute and the keys stay), instead of drawing them over each other."""
        optional = (self.volume, self.speed, self.shuffle, self.repeat, self.subs, self.audio)
        for w in optional:
            w.setHidden(False)
        lay = self.layout()
        for w in optional:
            lay.invalidate()
            if lay.minimumSize().width() <= width:
                break
            w.setHidden(True)

    def set_times(self, pos: float | None, length: float | None):
        self.cur.setText(clock(pos or 0))
        self.total.setText(clock(length) if length else "–:––")

    def set_playing(self, playing: bool):
        self.play.setIcon(glyph("pause" if playing else "play", 26))
        self.play.setToolTip(tr("grimoire.spells.playl.stage", "Pause (Space)") if playing else
                             tr("grimoire.spells.playl.stage", "Play (Space)"))

    def set_repeat(self, mode: str):
        self.repeat.setIcon(glyph("repeatone" if mode == "one" else "repeat", 20))
        self.repeat.setCheckable(True)
        self.repeat.setChecked(mode != "off")
        self.repeat.setToolTip({"off": tr("grimoire.spells.playl.stage", "Repeat: off"),
                                "all": tr("grimoire.spells.playl.stage", "Repeat: the whole queue"),
                                "one": tr("grimoire.spells.playl.stage", "Repeat: this one")}[mode])

    def set_volume(self, v, muted: bool):
        self.volume.blockSignals(True)
        if v is None:                     # no stream yet: keep the last value, grayed out
            self.volume.setEnabled(False)
            self.volume.setToolTip(tr("grimoire.spells.playl.stage",
                                      "The volume is PlayL's own stream in PipeWire; it can be set once something "
                                      "plays"))
        else:
            self.volume.setEnabled(True)
            self.volume.setValue(round(v))
            self.volume.setToolTip(tr("grimoire.spells.playl.stage", "Volume {n}%").format(n=round(v)))
        self.volume.blockSignals(False)
        self.mute.blockSignals(True)
        self.mute.setChecked(muted)
        self.mute.setIcon(glyph("muted" if muted else "audio", 20))
        self.mute.blockSignals(False)

    def paintEvent(self, _):
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(0, 0, 0, 0))
        g.setColorAt(0.45, QColor(0, 0, 0, 170))
        g.setColorAt(1, QColor(0, 0, 0, 225))
        p.fillRect(self.rect(), g)


class ArtView(QWidget):
    """A song: its grayscale cover (or a note glyph) with title, artist and album under it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.art: QPixmap | None = None
        self.title = self.artist = self.album = ""

    def set_info(self, title: str, artist: str, album: str):
        self.title, self.artist, self.album = title, artist, album
        self.update()

    def set_art(self, pm: QPixmap | None):
        self.art = pm if pm and not pm.isNull() else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#050505"))
        fm = self.fontMetrics()
        text_h = 90
        side = int(max(80, min(360, self.width() * 0.5, self.height() - text_h - 140)))
        x = (self.width() - side) / 2
        y = max(20.0, (self.height() - side - text_h - 100) / 2)
        box = QRectF(x, y, side, side)
        if self.art:
            pm = self.art.scaled(side * 2, side * 2, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(2)
            w, h = pm.width() / 2, pm.height() / 2
            p.drawPixmap(QRectF(x + (side - w) / 2, y + (side - h) / 2, w, h), pm, QRectF(pm.rect()))
            p.setPen(QColor("#1f1f1f"))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(box, 6, 6)
        else:
            p.setPen(QColor("#1f1f1f"))
            p.setBrush(QColor("#0f0f0f"))
            p.drawRoundedRect(box, 12, 12)
            g = int(side * 0.36)
            p.drawPixmap(int(x + (side - g) / 2), int(y + (side - g) / 2), _pixmap("music", "#4a4a4a", g))
        f = p.font()
        f.setPixelSize(22)
        f.setWeight(f.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        ty = y + side + 22
        p.drawText(QRectF(20, ty, self.width() - 40, 32), Qt.AlignmentFlag.AlignCenter,
                   p.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, self.width() - 40))
        f.setPixelSize(14)
        f.setWeight(f.Weight.Normal)
        p.setFont(f)
        p.setPen(QColor("#9a9a9a"))
        line = " · ".join(x for x in (self.artist, self.album) if x)
        p.drawText(QRectF(20, ty + 34, self.width() - 40, fm.height() + 8), Qt.AlignmentFlag.AlignCenter,
                   p.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, self.width() - 40))


class EmptyView(QWidget):
    """Nothing is playing: open something, or drop it here."""
    open_files = Signal()
    open_folder = Signal()
    open_url = Signal()

    def __init__(self, parent=None, message: str = "", command: str = ""):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        icon = QLabel()
        icon.setPixmap(_pixmap("playl", "#5a5a5a", 64))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon)
        lay.addSpacing(10)
        head = QLabel(tr("grimoire.spells.playl.stage", "Nothing playing") if not message else message)
        head.setObjectName("SectionTitle")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setWordWrap(True)
        lay.addWidget(head)
        if command:
            cmd = QLabel(command)
            cmd.setObjectName("Mono")
            cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cmd.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(cmd)
            row.addStretch(1)
            lay.addSpacing(8)
            lay.addLayout(row)
            lay.addStretch(1)
            return
        hint = QLabel(tr("grimoire.spells.playl.stage",
                         "Open a video or a song, a whole folder or a web address, or drop files here."))
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addSpacing(16)
        row = QHBoxLayout()
        row.addStretch(1)
        files = QPushButton(tr("grimoire.spells.playl.stage", "Open files…"))
        files.setObjectName("Primary")
        folder = QPushButton(tr("grimoire.spells.playl.stage", "Open folder…"))
        url = QPushButton(tr("grimoire.spells.playl.stage", "Open address…"))
        files.clicked.connect(self.open_files)
        folder.clicked.connect(self.open_folder)
        url.clicked.connect(self.open_url)
        for b in (files, folder, url):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)


class Stage(QWidget):
    """Video/art/empty underneath, controls on top; emits activity so the page can show the controls."""
    clicked = Signal()
    double_clicked = Signal()
    controls_shown = Signal(bool)         # over a video: subtitles move up out of their way
    dropped = Signal(list)
    start_over = Signal()

    def __init__(self, parent=None, message: str = "", command: str = ""):
        super().__init__(parent)
        self.setObjectName("Stage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#Stage { background: #000000; }")
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setMinimumSize(QSize(360, 240))
        self.video = VideoView(self)
        self.art = ArtView(self)
        self.empty = EmptyView(self, message, command)
        self.controls = Controls(self)
        self.bubble = Bubble(self)
        self.controls.bar.preview = self.bubble
        self.toast = QLabel(self)
        self.toast.setObjectName("Toast")
        self.toast.setTextFormat(Qt.TextFormat.PlainText)
        self.toast.setWordWrap(True)
        self.toast.hide()
        self._toast_timer = QTimer(self, singleShot=True, interval=6000, timeout=self.toast.hide)
        self.chip = QFrame(self)
        self.chip.setObjectName("Chip")
        cl = QHBoxLayout(self.chip)
        cl.setContentsMargins(12, 6, 6, 6)
        self.chip_text = QLabel()
        again = QPushButton(tr("grimoire.spells.playl.stage", "Start over"))
        again.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        again.clicked.connect(lambda: (self.chip.hide(), self.start_over.emit()))
        cl.addWidget(self.chip_text)
        cl.addWidget(again)
        self.chip.setStyleSheet(CONTROLS_QSS)
        self.chip.hide()
        self._chip_timer = QTimer(self, singleShot=True, interval=8000, timeout=self.chip.hide)
        self.mode = "empty"
        self.playing = False
        self.always_controls = False          # no player at all: nothing to hide
        self._hide_timer = QTimer(self, singleShot=True, interval=HIDE_AFTER_MS, timeout=self._idle)
        self._click_timer = QTimer(self, singleShot=True, timeout=self.clicked.emit)
        for w in (self.video, self.art):
            w.setMouseTracking(True)
            w.installEventFilter(self)
        self.set_mode("empty")

    # ------------------------------------------------------------ layout
    def resizeEvent(self, e):
        r = self.rect()
        for w in (self.video, self.art, self.empty):
            w.setGeometry(r)
        h = self.controls.sizeHint().height()
        self.controls.setGeometry(0, r.height() - h, r.width(), h)
        self._place_toast()
        self.chip.adjustSize()
        self.chip.move(16 if not self.isRightToLeft() else r.width() - self.chip.width() - 16, 16)
        super().resizeEvent(e)

    def _place_toast(self):
        w = min(560, self.width() - 32)
        self.toast.setFixedWidth(w)
        self.toast.adjustSize()
        self.toast.move((self.width() - w) // 2, 16)

    def set_mode(self, mode: str):
        """"empty", "video" or "audio"."""
        self.mode = mode
        self.video.setVisible(mode == "video")
        self.art.setVisible(mode == "audio")
        self.empty.setVisible(mode == "empty")
        self.controls.setVisible(mode != "empty")
        self.controls.raise_()
        self.toast.raise_()
        self.chip.raise_()
        self.activity()

    def set_playing(self, playing: bool):
        self.playing = playing
        self.activity()

    # ------------------------------------------------------------ hiding the controls over a video
    def activity(self):
        if self.mode != "empty" and not self.controls.isVisible():
            self.controls.show()
            self.controls_shown.emit(True)
        self.unsetCursor()
        if self.mode == "video" and self.playing:
            self._hide_timer.start()
        else:
            self._hide_timer.stop()

    def _idle(self):
        if self.mode != "video" or not self.playing:
            return
        busy = self.controls.bar.dragging or QApplication.activePopupWidget() is not None
        if busy or (self.controls.isVisible() and self.controls.underMouse()):
            self._hide_timer.start()          # a menu is open or the pointer rests on the controls
            return
        self.controls.hide()
        self.bubble.hide()
        self.controls_shown.emit(False)
        self.setCursor(QCursor(Qt.CursorShape.BlankCursor))

    def eventFilter(self, obj, e):
        t = e.type()
        if t == QEvent.Type.MouseMove:
            self.activity()
        elif t == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton:
            self._click_timer.start(250)                     # a double click (fullscreen) cancels it
        elif t == QEvent.Type.MouseButtonDblClick and e.button() == Qt.MouseButton.LeftButton:
            self._click_timer.stop()
            self.double_clicked.emit()
            return True
        return False

    def mouseMoveEvent(self, e):
        self.activity()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self.mode == "video" and self.playing:
            self._hide_timer.start(800)
        super().leaveEvent(e)

    # ------------------------------------------------------------ messages
    def say(self, text: str):
        self.toast.setText(text)
        self._place_toast()
        self.toast.show()
        self.toast.raise_()
        self._toast_timer.start()

    def resumed(self, pos: float):
        self.chip_text.setText(tr("grimoire.spells.playl.stage", "Resumed at {time}").format(time=ltr(clock(pos))))
        self.chip.adjustSize()
        self.chip.move(16 if not self.isRightToLeft() else self.width() - self.chip.width() - 16, 16)
        self.chip.show()
        self.chip.raise_()
        self._chip_timer.start()

    # ------------------------------------------------------------ drops
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u.toLocalFile() if u.isLocalFile() else u.toString() for u in e.mimeData().urls()]
        if urls:
            self.dropped.emit(urls)
            e.acceptProposedAction()
