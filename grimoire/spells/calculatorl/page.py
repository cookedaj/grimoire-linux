# SPDX-License-Identifier: GPL-3.0-or-later
"""CalculatorL's page: an expression line you type into (or click the keys), a live answer under it, Standard and
Scientific keypads, degrees/radians, history (click a line to reuse it), and conversions of units and currencies.

Keyboard: type anything the engine reads (2^10, sqrt(2), 15% of… as 15%*…, sin(30), 5!, pi), Enter for =, Esc
clears, Up/Down walk the history, Ctrl+C copies the answer when nothing is selected. History and the chosen modes
live in calculatorl.json.
"""
import json

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.paths import CONFIG
from grimoire.spells.calculatorl import engine, units
from grimoire.widgets import segments

SETTINGS = CONFIG / "calculatorl.json"
HISTORY_KEEP = 100
STANDARD = [["C", "⌫", "%", "÷"], ["7", "8", "9", "×"], ["4", "5", "6", "−"], ["1", "2", "3", "+"],
            ["±", "0", ".", "="]]
SCIENTIFIC = [["sin", "cos", "tan", "(", ")"], ["asin", "acos", "atan", "^", "√"], ["ln", "log", "π", "e", "!"],
              ["x²", "1/x", "ans", "mod", "abs"]]
INSERT = {"÷": "/", "×": "*", "−": "-", "π": "π", "e": "e", "^": "^", "√": "√", "!": "!", "(": "(", ")": ")",
          "mod": " mod ", "ans": "ans", "%": "%", ".": "."}


def load() -> dict:
    try:
        d = json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    hist = [h for h in d.get("history", []) if isinstance(h, list) and len(h) == 2
            and all(isinstance(x, str) for x in h)] if isinstance(d.get("history"), list) else []
    return {"scientific": bool(d.get("scientific", False)), "degrees": bool(d.get("degrees", True)),
            "history": hist[-HISTORY_KEEP:], "unit_cat": str(d.get("unit_cat", "length"))}


def save(s: dict):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, indent=1))
        tmp.replace(SETTINGS)
    except OSError:
        pass


def status_line() -> str:
    n = len(load()["history"])
    return tr("grimoire.spells.calculatorl.page", "%n calculation(s) in the history", n=n) if n else \
        tr("grimoire.spells.calculatorl.page", "Standard, scientific, units and currencies")


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class _Signals(QObject):
    rates = Signal(object)


class CalculatorLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.s = load()
        self.ans = 0.0
        self._hist_i = None
        self.sig = _Signals()
        self.sig.rates.connect(self._rates_done)
        root = QHBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 22)
        root.setSpacing(22)

        left = QVBoxLayout()
        left.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(_label("CalculatorL", "PageHeading"), 1)
        self.mode_btns = []
        for sci, text in ((False, tr("grimoire.spells.calculatorl.page", "Standard")),
                          (True, tr("grimoire.spells.calculatorl.page", "Scientific"))):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, sci=sci: self.set_scientific(sci))
            self.mode_btns.append(b)
            head.addWidget(b)
        segments(self.mode_btns)
        head.addSpacing(10)
        self.angle_btns = []
        for deg, text in ((True, "DEG"), (False, "RAD")):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setToolTip(tr("grimoire.spells.calculatorl.page", "Degrees") if deg
                         else tr("grimoire.spells.calculatorl.page", "Radians"))
            b.clicked.connect(lambda _=False, deg=deg: self.set_degrees(deg))
            self.angle_btns.append(b)
            head.addWidget(b)
        segments(self.angle_btns)
        left.addLayout(head)

        screen = QFrame()
        screen.setObjectName("Card")
        sv = QVBoxLayout(screen)
        sv.setContentsMargins(18, 14, 18, 14)
        self.expr = QLineEdit()
        self.expr.setObjectName("CalcExpr")
        self.expr.setLayoutDirection(Qt.LayoutDirection.LeftToRight)       # math reads left to right everywhere
        self.expr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.expr.setPlaceholderText(tr("grimoire.spells.calculatorl.page", "Type or tap a calculation"))
        self.expr.textChanged.connect(self._preview)
        self.expr.returnPressed.connect(self.equals)
        self.expr.installEventFilter(self)
        f = self.expr.font()
        f.setPointSizeF(f.pointSizeF() * 1.6)
        self.expr.setFont(f)
        self.result = _label("0", "Hero")
        self.result.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.result.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.hint = _label("", "Muted")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        sv.addWidget(self.expr)
        sv.addWidget(self.result)
        sv.addWidget(self.hint)
        left.addWidget(screen)

        pads = QHBoxLayout()
        pads.setSpacing(8)
        self.sci_pad = self._pad(SCIENTIFIC)
        pads.addWidget(self.sci_pad, 5)
        pads.addWidget(self._pad(STANDARD, primary="="), 4)
        left.addLayout(pads, 1)
        lw = QWidget()
        lw.setLayout(left)
        lw.setLayoutDirection(Qt.LayoutDirection.LeftToRight)              # a keypad never mirrors
        root.addWidget(lw, 3)

        right = QVBoxLayout()
        tabs = QHBoxLayout()
        self.side_btns = []
        for i, text in enumerate((tr("grimoire.spells.calculatorl.page", "History"),
                                  tr("grimoire.spells.calculatorl.page", "Convert"))):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, i=i: self._side(i))
            self.side_btns.append(b)
            tabs.addWidget(b)
        segments(self.side_btns)
        tabs.addStretch(1)
        right.addLayout(tabs)
        self.side = QStackedWidget()
        self.side.addWidget(self._history_view())
        self.side.addWidget(self._convert_view())
        right.addWidget(self.side, 1)
        rw = QWidget()
        rw.setLayout(right)
        rw.setMinimumWidth(300)
        root.addWidget(rw, 2)

        copy = QShortcut(QKeySequence.StandardKey.Copy, self)
        copy.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        copy.activated.connect(self._copy)
        self.set_scientific(self.s["scientific"], save_it=False)
        self.set_degrees(self.s["degrees"], save_it=False)
        self._side(0)
        self._fill_history()

    # ------------------------------------------------------------ keypad
    def _pad(self, rows, primary=None) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(6)
        for r, row in enumerate(rows):
            for c, key in enumerate(row):
                b = QPushButton(i18n.ltr(key))                 # RTL: "1/x" and "(" must not turn around
                b.setObjectName("Primary" if key == primary else "CalcKey")
                if key == primary:
                    b.setStyleSheet("font-size: 20px; border-radius: 12px;")
                b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                b.setMinimumHeight(44)
                b.setMaximumHeight(72)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)                  # typing stays in the expression line
                b.clicked.connect(lambda _=False, k=key: self.key(k))
                g.addWidget(b, r, c)
        return w

    def key(self, k: str):
        e = self.expr
        if k in ("÷", "×", "−", "+", "%", "^", "!", "mod", "x²") and e.text() and e.selectedText() == e.text():
            e.end(False)                                  # after =, an operator continues from the answer
        if k == "=":
            self.equals()
        elif k == "C":
            e.clear()
        elif k == "⌫":
            e.backspace()
        elif k == "±":
            t = e.text().strip()
            e.setText(t[2:-1] if t.startswith("-(") and t.endswith(")") else f"-({t})" if t else "-")
        elif k == "x²":
            e.insert("^2")
        elif k == "1/x":
            t = e.text().strip()
            e.setText(f"1/({t})" if t else "1/")
        elif k in ("sin", "cos", "tan", "asin", "acos", "atan", "ln", "log", "abs"):
            e.insert(k + "(")
        else:
            e.insert(INSERT.get(k, k))
        e.setFocus()

    # ------------------------------------------------------------ computing
    def _value(self, text: str) -> float:
        return engine.evaluate(text, degrees=self.s["degrees"], ans=self.ans)

    def _preview(self, text: str):
        self._hist_i = None
        if not text.strip():
            self.result.setText(engine.fmt(self.ans) if self.s["history"] else "0")
            self.hint.setText("")
            return
        try:
            self.result.setText(engine.fmt(self._value(text)))
            self.hint.setText("")
        except engine.CalcError:
            self.hint.setText("…")

    def equals(self):
        text = self.expr.text().strip()
        if not text:
            return
        try:
            x = self._value(text)
        except engine.CalcError as e:
            self.hint.setText(tr("grimoire.spells.calculatorl.page", "Can't work that out: {why}").format(why=e))
            return
        self.ans = x
        shown = engine.fmt(x)
        self.s["history"] = [*self.s["history"], [text, shown]][-HISTORY_KEEP:]
        save(self.s)
        self._fill_history()
        self.expr.setText(shown)
        self.expr.selectAll()                         # the next digit starts fresh, an operator continues
        self.result.setText(shown)
        self.hint.setText(text + " =")

    def _copy(self):
        if self.expr.hasSelectedText() and self.expr.hasFocus() and self.expr.selectedText() != self.expr.text():
            QGuiApplication.clipboard().setText(self.expr.selectedText())
        else:
            QGuiApplication.clipboard().setText(self.result.text())

    def eventFilter(self, obj, e):
        if obj is self.expr and e.type() == e.Type.KeyPress:
            if e.key() == Qt.Key.Key_Escape:
                self.expr.clear()
                return True
            if e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.s["history"]:
                n = len(self.s["history"])
                i = (n if self._hist_i is None else self._hist_i) + (-1 if e.key() == Qt.Key.Key_Up else 1)
                i = max(0, min(n - 1, i))
                self.expr.blockSignals(True)
                self.expr.setText(self.s["history"][i][0])
                self.expr.blockSignals(False)
                self._hist_i = i
                return True
            if e.text() in ("*", "/", "+", "-", "^", "%", "!") and self.expr.selectedText() == self.expr.text() \
                    and self.expr.text():
                self.expr.end(False)                  # after =, an operator continues from the answer
        return super().eventFilter(obj, e)

    # ------------------------------------------------------------ modes
    def set_scientific(self, on: bool, save_it=True):
        self.s["scientific"] = on
        self.sci_pad.setVisible(on)
        for b, sci in zip(self.mode_btns, (False, True)):
            b.setChecked(sci == on)
        for b in self.angle_btns:
            b.setVisible(on)
        if save_it:
            save(self.s)

    def set_degrees(self, on: bool, save_it=True):
        self.s["degrees"] = on
        for b, deg in zip(self.angle_btns, (True, False)):
            b.setChecked(deg == on)
        self._preview(self.expr.text())
        if save_it:
            save(self.s)

    def _side(self, i: int):
        self.side.setCurrentIndex(i)
        for j, b in enumerate(self.side_btns):
            b.setChecked(j == i)

    # ------------------------------------------------------------ history
    def _history_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 8, 0, 0)
        self.hist = QListWidget()
        self.hist.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.hist.itemClicked.connect(lambda it: self._reuse(it.data(Qt.ItemDataRole.UserRole)))
        v.addWidget(self.hist, 1)
        clear = QPushButton(tr("grimoire.spells.calculatorl.page", "Clear history"))
        clear.clicked.connect(self._clear_history)
        v.addWidget(clear)
        return w

    def _fill_history(self):
        self.hist.clear()
        for expr, res in reversed(self.s["history"]):
            it = QListWidgetItem(f"{expr}\n= {res}")
            it.setData(Qt.ItemDataRole.UserRole, res)
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            self.hist.addItem(it)
        if not self.s["history"]:
            it = QListWidgetItem(tr("grimoire.spells.calculatorl.page", "Your calculations show up here."))
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.hist.addItem(it)

    def _reuse(self, value):
        if value:
            self.expr.insert(value)
            self.expr.setFocus()

    def _clear_history(self):
        self.s["history"] = []
        save(self.s)
        self._fill_history()

    # ------------------------------------------------------------ conversions
    def _convert_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(8)
        self.cat = QComboBox()
        for key, (name, _u) in units.CATEGORIES.items():
            self.cat.addItem(tr("grimoire.spells.calculatorl.units", name), key)
        self.cat.addItem(tr("grimoire.spells.calculatorl.page", "Currency"), "currency")
        v.addWidget(self.cat)
        self.c_in = QLineEdit("1")
        self.c_in.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.c_from = QComboBox()
        self.c_to = QComboBox()
        swap = QPushButton("⇅")
        swap.setToolTip(tr("grimoire.spells.calculatorl.page", "Swap"))
        swap.clicked.connect(self._swap)
        row = QHBoxLayout()
        row.addWidget(self.c_in, 1)
        row.addWidget(self.c_from)
        v.addLayout(row)
        mid = QHBoxLayout()
        mid.addStretch(1)
        mid.addWidget(swap)
        v.addLayout(mid)
        self.c_out = _label("", "Hero")
        self.c_out.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.c_out.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row2 = QHBoxLayout()
        row2.addWidget(self.c_out, 1)
        row2.addWidget(self.c_to)
        v.addLayout(row2)
        self.rates_note = _label("", "Muted", wrap=True)
        self.rates_btn = QPushButton(tr("grimoire.spells.calculatorl.page", "Update rates"))
        self.rates_btn.clicked.connect(self._update_rates)
        v.addWidget(self.rates_note)
        v.addWidget(self.rates_btn)
        v.addStretch(1)
        self.cat.currentIndexChanged.connect(self._fill_units)
        for wdg in (self.c_from, self.c_to):
            wdg.currentIndexChanged.connect(self._convert)
        self.c_in.textChanged.connect(self._convert)
        i = self.cat.findData(self.s["unit_cat"])
        self.cat.setCurrentIndex(i if i >= 0 else 0)
        self._fill_units()
        return w

    def _fill_units(self):
        key = self.cat.currentData()
        self.s["unit_cat"] = key
        save(self.s)
        currency = key == "currency"
        self.rates_btn.setVisible(currency)
        self.rates_note.setVisible(currency)
        for box in (self.c_from, self.c_to):
            box.blockSignals(True)
            box.clear()
        if currency:
            rates = units.cached_rates()
            codes = sorted(rates.get("rates", {}))
            for box in (self.c_from, self.c_to):
                box.addItems(codes)
            if codes:
                self.c_from.setCurrentText("USD" if "USD" in codes else codes[0])
                self.c_to.setCurrentText("EUR")
            self.rates_note.setText(
                tr("grimoire.spells.calculatorl.page", "European Central Bank reference rates of {date}.").format(
                    date=i18n.ltr(rates["date"])) if rates else
                tr("grimoire.spells.calculatorl.page", "No rates yet: press Update rates. It downloads the European "
                                                       "Central Bank's daily reference rates (nothing is sent)."))
        else:
            for k, (label, _f) in units.CATEGORIES[key][1].items():
                self.c_from.addItem(i18n.ltr(label), k)
                self.c_to.addItem(i18n.ltr(label), k)
            self.c_to.setCurrentIndex(min(1, self.c_to.count() - 1))
        for box in (self.c_from, self.c_to):
            box.blockSignals(False)
        self._convert()

    def _convert(self, *_):
        key = self.cat.currentData()
        try:
            value = self._value(self.c_in.text() or "0")
            if key == "currency":
                rates = units.cached_rates()
                if not rates or not self.c_from.currentText():
                    self.c_out.setText("—")
                    return
                out = units.convert_currency(rates, value, self.c_from.currentText(), self.c_to.currentText())
                self.c_out.setText(f"{out:,.2f}")
            else:
                out = units.convert(key, value, self.c_from.currentData(), self.c_to.currentData())
                self.c_out.setText(engine.fmt(out, 10))
        except (engine.CalcError, KeyError, ZeroDivisionError):
            self.c_out.setText("—")

    def _swap(self):
        a, b = self.c_from.currentIndex(), self.c_to.currentIndex()
        self.c_from.setCurrentIndex(b)
        self.c_to.setCurrentIndex(a)

    def _update_rates(self):
        self.rates_btn.setEnabled(False)
        self.rates_note.setText(tr("grimoire.spells.calculatorl.page", "Downloading the rates…"))

        def work():
            try:
                return units.update_rates()
            except (OSError, ValueError) as e:
                return str(e)
        POOL.start(Job(work, self.sig.rates.emit))

    def _rates_done(self, result):
        self.rates_btn.setEnabled(True)
        if isinstance(result, str):
            self.rates_note.setText(tr("grimoire.spells.calculatorl.page", "Couldn't download the rates: {err}")
                                    .format(err=result))
            return
        self._fill_units()

