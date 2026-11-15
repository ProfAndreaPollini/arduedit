"""Dialogo di ricerca e installazione di librerie da indice Arduino."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from arduedit.core.library_search import RisultatoRicerca, cerca_librerie


class _SegnaliRicerca(QObject):
    completata = Signal(list)  # list[RisultatoRicerca]
    errore = Signal(str)


class RicercaTask(QRunnable):
    def __init__(self, arduino_cli: Path, query: str):
        super().__init__()
        self.arduino_cli = arduino_cli
        self.query = query
        self.segnali = _SegnaliRicerca()

    def run(self) -> None:
        try:
            risultati = cerca_librerie(self.arduino_cli, self.query)
            self.segnali.completata.emit(risultati)
        except Exception as exc:  # noqa: BLE001
            self.segnali.errore.emit(str(exc))


class LibrarySearchDialog(QDialog):
    libreria_scelta = Signal(str)  # nome della libreria scelta

    def __init__(self, arduino_cli: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cerca libreria")
        self.resize(820, 520)
        self.arduino_cli = arduino_cli
        self._task: RicercaTask | None = None

        layout = QVBoxLayout(self)

        # Barra di ricerca
        riga = QHBoxLayout()
        self.edit_query = QLineEdit()
        self.edit_query.setPlaceholderText("Cerca per nome, autore o header (es. 'DHT', 'name:Servo')")
        self.edit_query.returnPressed.connect(self._cerca)
        self.btn_cerca = QPushButton("🔍 Cerca")
        self.btn_cerca.clicked.connect(self._cerca)
        riga.addWidget(self.edit_query, stretch=1)
        riga.addWidget(self.btn_cerca)
        layout.addLayout(riga)

        # Tabella risultati
        self.tabella = QTableWidget(0, 3)
        self.tabella.setHorizontalHeaderLabels(["Libreria", "Versione", "Descrizione"])
        self.tabella.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabella.horizontalHeader().setStretchLastSection(True)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabella.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabella.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabella)

        # Pulsanti
        pulsanti = QHBoxLayout()
        self.btn_installa = QPushButton("📦 Installa nel progetto")
        self.btn_installa.setEnabled(False)
        self.btn_installa.clicked.connect(self._installa)
        self.tabella.itemSelectionChanged.connect(lambda: self.btn_installa.setEnabled(self.tabella.currentRow() >= 0))
        btn_chiudi = QPushButton("Chiudi")
        btn_chiudi.clicked.connect(self.reject)
        pulsanti.addWidget(self.btn_installa)
        pulsanti.addStretch()
        pulsanti.addWidget(btn_chiudi)
        layout.addLayout(pulsanti)

        self.lbl_stato = QLabel("")
        layout.addWidget(self.lbl_stato)

    @Slot()
    def _cerca(self):
        query = self.edit_query.text().strip()
        if not query:
            return
        self.btn_cerca.setEnabled(False)
        self.btn_installa.setEnabled(False)
        self.lbl_stato.setText("Ricerca in corso…")
        self.tabella.setRowCount(0)

        task = RicercaTask(self.arduino_cli, query)
        task.segnali.completata.connect(self._on_risultati)
        task.segnali.errore.connect(self._on_errore)
        self._task = task
        QThreadPool.globalInstance().start(task)

    @Slot(list)
    def _on_risultati(self, risultati: list[RisultatoRicerca]):
        self.btn_cerca.setEnabled(True)
        self._task = None
        self.lbl_stato.setText(f"{len(risultati)} risultati.")
        self.tabella.setRowCount(len(risultati))
        for r, lib in enumerate(risultati):
            self.tabella.setItem(r, 0, QTableWidgetItem(lib.nome))
            self.tabella.setItem(r, 1, QTableWidgetItem(lib.versione or "—"))
            desc = lib.descrizione or ""
            if len(desc) > 140:
                desc = desc[:137] + "…"
            self.tabella.setItem(r, 2, QTableWidgetItem(desc))
            # Conserva il nome per l'installazione
            self.tabella.item(r, 0).setData(Qt.UserRole, lib.nome)

    @Slot(str)
    def _on_errore(self, msg: str):
        self.btn_cerca.setEnabled(True)
        self._task = None
        self.lbl_stato.setText(f"Errore: {msg}")

    def _installa(self):
        riga = self.tabella.currentRow()
        if riga < 0:
            return
        nome = self.tabella.item(riga, 0).data(Qt.UserRole)
        if nome:
            self.libreria_scelta.emit(nome)
            self.accept()
