"""Pannello del monitor seriale con toolbar e area di testo."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from arduedit.core.serial_monitor import RigaSeriale, SerialMonitorProcess

BAUD_COMUNI = [9600, 19200, 38400, 57600, 115200]


class SerialPanel(QWidget):
    def __init__(self, arduino_cli: Path, parent=None):
        super().__init__(parent)
        self.monitor = SerialMonitorProcess(arduino_cli, self)
        self.monitor.riga_ricevuta.connect(self._on_riga)
        self.monitor.aperto.connect(self._on_aperto)  # riabilitato
        self.monitor.chiuso.connect(self._on_chiuso)
        self.monitor.errore.connect(self._on_errore)

        self._mostra_timestamp = False
        self._filtro = ""
        self._righe: list[RigaSeriale] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Toolbar ---
        barra = QHBoxLayout()
        self.lbl_stato = QLabel("Monitor chiuso")
        self.combo_baud = QComboBox()
        for b in BAUD_COMUNI:
            self.combo_baud.addItem(str(b), userData=b)
        self.combo_baud.setCurrentText("9600")
        self.combo_baud.currentIndexChanged.connect(self._cambia_baud)

        self.chk_timestamp = QCheckBox("Timestamp")
        self.chk_timestamp.toggled.connect(self._toggle_timestamp)

        self.edit_filtro = QLineEdit()
        self.edit_filtro.setPlaceholderText("Filtra…")
        self.edit_filtro.textChanged.connect(self._on_filtro)

        self.btn_registra = QPushButton("🔴 Registra")
        self.btn_registra.setCheckable(True)
        self.btn_registra.toggled.connect(self._toggle_registrazione)

        btn_pulisci = QPushButton("🗑 Pulisci")
        btn_pulisci.clicked.connect(self._pulisci)

        barra.addWidget(self.lbl_stato)
        barra.addWidget(QLabel("Baud:"))
        barra.addWidget(self.combo_baud)
        barra.addWidget(self.chk_timestamp)
        barra.addWidget(self.edit_filtro, stretch=1)
        barra.addWidget(self.btn_registra)
        barra.addWidget(btn_pulisci)
        layout.addLayout(barra)

        # --- Area di testo ---
        self.area = QPlainTextEdit(readOnly=True)
        self.area.setMaximumBlockCount(5000)
        self.area.setStyleSheet("font-family: Consolas, monospace; font-size: 11pt;")
        layout.addWidget(self.area)

        # Auto-scroll intelligente
        self._auto_scroll = True
        self.area.verticalScrollBar().valueChanged.connect(self._on_scroll)

    # --------------------------------------------------------------- API

    # def apri(self, porta: str, baud: int | None = None) -> None:
    #     baud = baud or self.combo_baud.currentData()
    #     self.monitor.apri(porta, baud)

    # def chiudi(self) -> None:
    #     self.monitor.chiudi()

    def is_open(self) -> bool:
        return self.monitor.is_open()

    # --------------------------------------------------------------- toolbar

    def _cambia_baud(self):
        if not self.monitor.is_open():
            return
        porta = self.monitor.porta
        self.monitor.chiudi()
        self.monitor.apri(porta, self.combo_baud.currentData())

    def _toggle_timestamp(self, attivo: bool):
        self._mostra_timestamp = attivo
        self._ridisegna()

    def _on_filtro(self, testo: str):
        self._filtro = testo.strip().lower()
        self._ridisegna()

    def _pulisci(self):
        self._righe.clear()
        self.area.clear()

    def closeEvent(self, event):
        self.monitor.chiudi()
        super().closeEvent(event)

    # --------------------------------------------------------------- ricezione

    def _on_riga(self, testo: str):
        riga = RigaSeriale(testo=testo, timestamp=datetime.now())
        self._righe.append(riga.testo)
        if len(self._righe) > 5000:
            del self._righe[:1000]
        if self._filtro and self._filtro not in testo.lower():
            return
        self._append_riga(riga)

    def apri(self, porta: str, baud: int | None = None) -> None:
        baud = baud or self.combo_baud.currentData()
        self.monitor.apri(porta, baud)

    def chiudi(self) -> None:
        self.monitor.chiudi()

    def _append_riga(self, riga: RigaSeriale):
        testo = riga.testo
        if self._mostra_timestamp:
            testo = f"[{riga.timestamp:%H:%M:%S.%f}"[:-3] + f"] {testo}"
        scrollbar = self.area.verticalScrollBar()
        era_in_fondo = scrollbar.value() >= scrollbar.maximum() - 4
        self.area.appendPlainText(testo)
        if era_in_fondo and self._auto_scroll:
            self.area.ensureCursorVisible()

    def _ridisegna(self):
        self.area.clear()
        for riga in self._righe:
            if self._filtro and self._filtro not in riga.testo.lower():
                continue
            testo = riga.testo
            if self._mostra_timestamp:
                testo = f"[{riga.timestamp:%H:%M:%S.%f}"[:-3] + f"] {testo}"
            self.area.appendPlainText(testo)

    # --------------------------------------------------------------- stato

    @Slot(str, int)
    def _on_aperto(self, porta: str, baud: int):
        self.lbl_stato.setText(f"📡 {porta} · {baud} baud")
        self.combo_baud.setCurrentText(str(baud))

    @Slot(str)
    def _on_riga(self, testo: str):
        riga = RigaSeriale(testo=testo, timestamp=datetime.now())
        self._righe.append(riga)  # ← RigaSeriale, non str
        if len(self._righe) > 5000:
            del self._righe[:1000]
        if self._filtro and self._filtro not in testo.lower():
            return
        self._append_riga(riga)

    def _ridisegna(self):
        self.area.clear()
        for riga in self._righe:
            if self._filtro and self._filtro not in riga.testo.lower():
                continue
            testo = riga.testo
            if self._mostra_timestamp:
                testo = f"[{riga.timestamp:%H:%M:%S.%f}"[:-3] + f"] {testo}"
            self.area.appendPlainText(testo)

    @Slot()
    def _on_chiuso(self):
        self.lbl_stato.setText("Monitor chiuso")

    @Slot(str)
    def _on_errore(self, msg: str):
        self.lbl_stato.setText(f"⚠ {msg}")

    # --------------------------------------------------------------- CSV

    def _toggle_registrazione(self, attivo: bool):
        pass
        # if attivo:
        #     cartella = QFileDialog.getExistingDirectory(
        #         self,
        #         "Cartella dove salvare i dati",
        #         str(Path.home()),
        #     )
        #     if not cartella:
        #         self.btn_registra.setChecked(False)
        #         return
        #     percorso = self.monitor.avvia_registrazione(Path(cartella))
        #     self.btn_registra.setText("⏹ Stop")
        #     self.lbl_stato.setText(f"🔴 Registrazione: {percorso.name}")
        # else:
        #     percorso = self.monitor.chiudi_registrazione()
        #     self.btn_registra.setText("🔴 Registra")
        #     if percorso:
        #         self.lbl_stato.setText(f"✅ Salvato: {percorso.name}")

    # --------------------------------------------------------------- scroll

    def _on_scroll(self, valore: int):
        sb = self.area.verticalScrollBar()
        self._auto_scroll = valore >= sb.maximum() - 4
