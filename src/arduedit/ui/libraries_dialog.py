"""Dialogo di gestione delle librerie locali al progetto."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from arduedit.core.project_libraries import (
    elenca_librerie,
    installa_da_zip,
    rimuovi_libreria,
)


class LibrerieDialog(QDialog):
    """Gestisce le librerie del progetto. La ricerca online è delegata alla MainWindow."""

    # Emesso quando l'utente preme "Cerca online". La MainWindow apre il
    # dialogo di ricerca, scarica e poi richiama self.aggiorna().
    ricerca_online_richiesta = Signal()

    def __init__(self, progetto: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Librerie del progetto")
        self.resize(680, 440)
        self.progetto = progetto

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Le librerie elencate sono disponibili solo per questo progetto.\n"
            "Aggiungi uno ZIP scaricato manualmente oppure cerca nell'indice Arduino."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabella = QTableWidget(0, 3)
        self.tabella.setHorizontalHeaderLabels(["Libreria", "Versione", "Cartella"])
        self.tabella.horizontalHeader().setStretchLastSection(True)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabella.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabella.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabella)

        pulsanti = QHBoxLayout()
        btn_cerca = QPushButton("🔍 Cerca nell'indice…")
        btn_cerca.clicked.connect(self.ricerca_online_richiesta)
        btn_aggiungi = QPushButton("➕ Aggiungi da ZIP…")
        btn_aggiungi.clicked.connect(self._aggiungi)
        btn_rimuovi = QPushButton("🗑 Rimuovi selezionata")
        btn_rimuovi.clicked.connect(self._rimuovi)
        btn_cartella = QPushButton("📂 Apri cartella")
        btn_cartella.clicked.connect(self._apri_cartella)

        pulsanti.addWidget(btn_cerca)
        pulsanti.addWidget(btn_aggiungi)
        pulsanti.addWidget(btn_rimuovi)
        pulsanti.addStretch()
        pulsanti.addWidget(btn_cartella)
        layout.addLayout(pulsanti)

        chiudi = QPushButton("Chiudi")
        chiudi.clicked.connect(self.accept)
        layout.addWidget(chiudi, alignment=Qt.AlignRight)

        self.aggiorna()

    def aggiorna(self):
        """Ricarica la tabella. Pubblico: la MainWindow lo chiama dopo un download."""
        librerie = elenca_librerie(self.progetto)
        self.tabella.setRowCount(len(librerie))
        for r, lib in enumerate(librerie):
            self.tabella.setItem(r, 0, QTableWidgetItem(lib.nome))
            self.tabella.setItem(r, 1, QTableWidgetItem(lib.versione or "—"))
            self.tabella.setItem(r, 2, QTableWidgetItem(lib.cartella.name))
            self.tabella.item(r, 0).setData(Qt.UserRole, lib.cartella.name)

    def _aggiungi(self):
        percorso, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona il file ZIP della libreria",
            str(Path.home()),
            "Archivi ZIP (*.zip)",
        )
        if not percorso:
            return
        try:
            lib = installa_da_zip(self.progetto, Path(percorso))
        except ValueError as exc:
            QMessageBox.warning(self, "Impossibile aggiungere la libreria", str(exc))
            return
        self.aggiorna()
        QMessageBox.information(
            self,
            "Libreria aggiunta",
            f"La libreria '{lib.nome}' è ora disponibile per questo progetto.",
        )

    def _rimuovi(self):
        riga = self.tabella.currentRow()
        if riga < 0:
            QMessageBox.information(self, "Nessuna selezione", "Seleziona una libreria da rimuovere.")
            return
        nome_cartella = self.tabella.item(riga, 0).data(Qt.UserRole)
        nome_visibile = self.tabella.item(riga, 0).text()

        conferma = QMessageBox.question(
            self,
            "Rimuovere la libreria?",
            f"Vuoi rimuovere '{nome_visibile}' dal progetto?\nL'operazione non può essere annullata.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if conferma != QMessageBox.Yes:
            return
        try:
            rimuovi_libreria(self.progetto, nome_cartella)
        except ValueError as exc:
            QMessageBox.warning(self, "Impossibile rimuovere", str(exc))
            return
        self.aggiorna()

    def _apri_cartella(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.progetto / "libraries")))
