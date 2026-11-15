"""Autocompletamento delle API Arduino per QPlainTextEdit."""

from __future__ import annotations

import json
import logging

from importlib.resources import files

from PySide6.QtCore import QEvent, QModelIndex, QObject, Qt, QTimer, Slot
from PySide6.QtGui import (
    QColor,
    QFont,
    QStandardItem,
    QStandardItemModel,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCompleter,
    QPlainTextEdit,
    QStyle,
    QStyledItemDelegate,
)

log = logging.getLogger(__name__)

RUOLO_FIRMA = Qt.UserRole + 1
RUOLO_DESCRIZIONE = Qt.UserRole + 2


class ApiItemDelegate(QStyledItemDelegate):
    """Disegna ogni suggerimento su due righe: nome + firma, poi descrizione."""

    def paint(self, painter, option, index: QModelIndex):
        if not index.isValid():
            return

        painter.save()

        selezionato = bool(option.state & QStyle.State_Selected)
        if selezionato:
            painter.fillRect(option.rect, QColor("#2e7d32"))
            colore_nome = QColor("white")
            colore_firma = QColor("#c8e6c9")
            colore_desc = QColor("#c8e6c9")
        else:
            if option.state & QStyle.State_MouseOver:
                painter.fillRect(option.rect, QColor("#f5f5f5"))
            colore_nome = QColor("#000000")
            colore_firma = QColor("#666666")
            colore_desc = QColor("#888888")

        nome = index.data(Qt.DisplayRole) or ""
        firma = index.data(RUOLO_FIRMA) or ""
        descrizione = index.data(RUOLO_DESCRIZIONE) or ""

        rect = option.rect.adjusted(8, 4, -8, -4)

        # Riga 1: nome in grassetto monospace + firma in grigio
        font_nome = QFont("Consolas", 11)
        font_nome.setBold(True)
        painter.setFont(font_nome)
        painter.setPen(colore_nome)

        larghezza_nome = option.fontMetrics.horizontalAdvance(nome) + 12
        painter.drawText(
            rect.left(),
            rect.top(),
            rect.width(),
            20,
            Qt.AlignLeft | Qt.AlignVCenter,
            nome,
        )

        if firma:
            font_firma = QFont("Consolas", 10)
            painter.setFont(font_firma)
            painter.setPen(colore_firma)
            painter.drawText(
                rect.left() + larghezza_nome,
                rect.top(),
                rect.width() - larghezza_nome,
                20,
                Qt.AlignLeft | Qt.AlignVCenter,
                firma,
            )

        # Riga 2: descrizione, troncata se troppo lunga
        if descrizione:
            font_desc = QFont("Segoe UI", 9)
            painter.setFont(font_desc)
            painter.setPen(colore_desc)
            desc_troncata = option.fontMetrics.elidedText(
                descrizione,
                Qt.ElideRight,
                rect.width(),
            )
            painter.drawText(
                rect.left(),
                rect.top() + 20,
                rect.width(),
                18,
                Qt.AlignLeft | Qt.AlignVCenter,
                desc_troncata,
            )

        painter.restore()

    def sizeHint(self, option, index: QModelIndex):
        return option.rect.size().expandedTo(option.rect.size().__class__(300, 44))


class ArduinoCompleter(QObject):
    def __init__(self, editor: QPlainTextEdit, parent=None):
        super().__init__(parent or editor)
        self._editor = editor
        self._api = self._carica_api()
        self._prefix = ""

        model = QStandardItemModel(self)
        for nome in sorted(self._api.keys()):
            info = self._api[nome]
            item = QStandardItem(nome)
            item.setEditable(False)
            item.setData(info.get("firma", ""), RUOLO_FIRMA)
            item.setData(info.get("descrizione", ""), RUOLO_DESCRIZIONE)
            model.appendRow(item)

        self._completer = QCompleter(model, self)
        self._completer.setWidget(editor)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchStartsWith)
        self._completer.setCompletionRole(Qt.DisplayRole)
        self._completer.activated.connect(self._inserisci)

        popup = self._completer.popup()
        popup.setItemDelegate(ApiItemDelegate(popup))
        popup.setStyleSheet("QListView { background: #ffffff; color: #000000; border: 1px solid #ccc; }")
        popup.setMinimumWidth(420)
        popup.setMaximumHeight(320)

        editor.installEventFilter(self)

    # ------------------------------------------------------------- API

    def _carica_api(self) -> dict:
        try:
            percorso = files("arduedit.resources") / "api_arduino.json"
            with percorso.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Impossibile caricare api_arduino.json: %s", exc)
            return {}

    # ------------------------------------------------------------- eventi

    def eventFilter(self, obj, event):
        if obj is not self._editor:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier:
                self._mostra(prefix="")
                return True

            testo = event.text()
            if testo and (testo.isalnum() or testo in "_."):
                QTimer.singleShot(0, self._auto_trigger)

        return super().eventFilter(obj, event)

    def _auto_trigger(self):
        self._mostra(prefix=self._prefisso_corrente())

    def _prefisso_corrente(self) -> str:
        """Prefisso digitato: alfanumerico + underscore + punto (per Serial.print)."""
        cursor = self._editor.textCursor()
        pos = cursor.position()
        testo = self._editor.toPlainText()

        # Risali fino a un carattere non valido
        inizio = pos
        while inizio > 0 and (testo[inizio - 1].isalnum() or testo[inizio - 1] in "_."):
            inizio -= 1
        return testo[inizio:pos]

    # ------------------------------------------------------------- popup

    def _mostra(self, prefix: str):
        if len(prefix) < 2 and prefix != "":
            self._completer.popup().hide()
            return
        self._prefix = prefix
        self._completer.setCompletionPrefix(prefix)
        if self._completer.completionCount() == 0:
            self._completer.popup().hide()
            return

        rect = self._editor.cursorRect()
        popup = self._completer.popup()
        rect.setWidth(max(420, popup.sizeHintForColumn(0) + 40))
        rect.setHeight(44)
        self._completer.complete(rect)

    @Slot(str)
    def _inserisci(self, testo: str):
        cursor = self._editor.textCursor()
        for _ in range(len(self._prefix)):
            cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
        cursor.insertText(testo)
        self._editor.setTextCursor(cursor)
