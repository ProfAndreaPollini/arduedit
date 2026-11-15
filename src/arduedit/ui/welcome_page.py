"""Schermata iniziale di ArduEdit: nuovo progetto, apri progetto, recenti."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomePage(QWidget):
    nuovo_progetto_richiesto = Signal()
    apri_progetto_richiesto = Signal()
    progetto_recente_scelto = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(20)

        titolo = QLabel("ArduEdit")
        titolo.setStyleSheet("font-size: 36pt; font-weight: bold; color: #2e7d32;")
        layout.addWidget(titolo)

        sottotitolo = QLabel("Scegli un progetto per iniziare")
        sottotitolo.setStyleSheet("font-size: 14pt; color: #666;")
        layout.addWidget(sottotitolo)
        layout.addSpacing(12)

        pulsanti = QHBoxLayout()
        self.btn_nuovo = QPushButton("➕  Nuovo progetto")
        self.btn_nuovo.setMinimumHeight(52)
        self.btn_nuovo.setStyleSheet("font-size: 14pt; padding: 10px 24px;")
        self.btn_nuovo.clicked.connect(self.nuovo_progetto_richiesto)

        self.btn_apri = QPushButton("📂  Apri progetto esistente")
        self.btn_apri.setMinimumHeight(52)
        self.btn_apri.setStyleSheet("font-size: 14pt; padding: 10px 24px;")
        self.btn_apri.clicked.connect(self.apri_progetto_richiesto)

        pulsanti.addWidget(self.btn_nuovo)
        pulsanti.addWidget(self.btn_apri)
        pulsanti.addStretch()
        layout.addLayout(pulsanti)

        layout.addSpacing(24)
        layout.addWidget(QLabel("Progetti recenti:"))
        self.lista_recenti = QListWidget()
        self.lista_recenti.setStyleSheet("font-size: 12pt;")
        self.lista_recenti.itemDoubleClicked.connect(self._on_recente_scelto)
        layout.addWidget(self.lista_recenti, stretch=1)

    def set_recenti(self, percorsi: list[Path]) -> None:
        self.lista_recenti.clear()
        if not percorsi:
            item = QListWidgetItem("(nessun progetto recente)")
            item.setFlags(Qt.NoItemFlags)
            self.lista_recenti.addItem(item)
            return
        for p in percorsi:
            item = QListWidgetItem(f"{p.name}    —    {p}")
            item.setData(Qt.UserRole, p)
            self.lista_recenti.addItem(item)

    def _on_recente_scelto(self, item: QListWidgetItem) -> None:
        percorso = item.data(Qt.UserRole)
        if isinstance(percorso, Path):
            self.progetto_recente_scelto.emit(percorso)
