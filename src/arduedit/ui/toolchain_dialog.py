"""Dialogo di gestione toolchain, riservato all'insegnante."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from arduedit.core.toolchain import (
    CORE_CONSIGLIATI,
    CoreInfo,
    comando_installazione,
    costruisci_proxy_url,
    lista_core_installati,
)


class ToolchainDialog(QDialog):
    def __init__(self, arduino_cli: Path | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestione toolchain")
        self.resize(760, 520)
        self.arduino_cli = arduino_cli

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._installato_qualcosa = False

        # --- Tab 1: installati ---
        self.tab_installati = QWidget()
        lay1 = QVBoxLayout(self.tab_installati)
        self.tabella = QTableWidget(0, 3)
        self.tabella.setHorizontalHeaderLabels(["Core", "Versione installata", "Aggiornamento"])
        self.tabella.horizontalHeader().setStretchLastSection(True)
        self.tabella.setEditTriggers(QTableWidget.NoEditTriggers)
        lay1.addWidget(self.tabella)
        btn_aggiorna_lista = QPushButton("⟳ Aggiorna elenco")
        btn_aggiorna_lista.clicked.connect(self._carica_installati)
        lay1.addWidget(btn_aggiorna_lista)

        # --- Tab 2: installa ---
        self.tab_installa = QWidget()
        lay2 = QFormLayout(self.tab_installa)

        self.combo_core = QComboBox()
        for c in CORE_CONSIGLIATI:
            self.combo_core.addItem(c["nome"], userData=c)
        lay2.addRow("Core da installare:", self.combo_core)

        # Campi proxy (opzionali, ma necessari in molte scuole)
        self.chk_proxy = QCheckBox("Usa proxy per il download")
        lay2.addRow(self.chk_proxy)

        self.edit_host = QLineEdit()
        self.edit_host.setPlaceholderText("proxy.scuola.local")
        self.spin_porta = QSpinBox()
        self.spin_porta.setRange(1, 65535)
        self.spin_porta.setValue(8080)
        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText("utente")
        self.edit_pass = QLineEdit()
        self.edit_pass.setEchoMode(QLineEdit.Password)
        self.edit_pass.setPlaceholderText("password")

        riga_proxy = QHBoxLayout()
        riga_proxy.addWidget(QLabel("Host:"))
        riga_proxy.addWidget(self.edit_host)
        riga_proxy.addWidget(QLabel("Porta:"))
        riga_proxy.addWidget(self.spin_porta)
        lay2.addRow(riga_proxy)
        riga_auth = QHBoxLayout()
        riga_auth.addWidget(QLabel("Utente:"))
        riga_auth.addWidget(self.edit_user)
        riga_auth.addWidget(QLabel("Password:"))
        riga_auth.addWidget(self.edit_pass)
        lay2.addRow(riga_auth)

        for w in (self.edit_host, self.spin_porta, self.edit_user, self.edit_pass):
            w.setEnabled(False)
        self.chk_proxy.toggled.connect(
            lambda on: [w.setEnabled(on) for w in (self.edit_host, self.spin_porta, self.edit_user, self.edit_pass)]
        )

        self.btn_installa = QPushButton("Installa core selezionato")
        self.btn_installa.clicked.connect(self._installa)
        lay2.addRow(self.btn_installa)

        self.console = QPlainTextEdit(readOnly=True)
        self.console.setMaximumBlockCount(2000)
        lay2.addRow(QLabel("Avanzamento:"))
        lay2.addRow(self.console)

        self.tabs.addTab(self.tab_installati, "Installati")
        self.tabs.addTab(self.tab_installa, "Installa")

        # --- Chiusura ---
        btn_chiudi = QPushButton("Chiudi")
        btn_chiudi.clicked.connect(self.accept)
        layout.addWidget(btn_chiudi, alignment=Qt.AlignRight)

        self._processo: QProcess | None = None
        self._carica_installati()

    # --------------------------------------------------------------- tab 1

    def _carica_installati(self):
        if self.arduino_cli is None:
            self.tabella.setRowCount(1)
            self.tabella.setItem(0, 0, QTableWidgetItem("arduino-cli non trovato"))
            return
        cores = lista_core_installati(self.arduino_cli)
        self.tabella.setRowCount(len(cores))
        for r, c in enumerate(cores):
            self.tabella.setItem(r, 0, QTableWidgetItem(c.id))
            self.tabella.setItem(r, 1, QTableWidgetItem(c.installed_version or "—"))
            if c.aggiornabile:
                self.tabella.setItem(r, 2, QTableWidgetItem(f"→ {c.latest_version}"))
            else:
                self.tabella.setItem(r, 2, QTableWidgetItem(""))

    # --------------------------------------------------------------- tab 2

    def _installa(self):
        if self.arduino_cli is None:
            QMessageBox.warning(self, "arduino-cli assente", "Impossibile installare core senza arduino-cli.")
            return
        if self._processo is not None and self._processo.state() != QProcess.NotRunning:
            QMessageBox.information(
                self, "Installazione in corso", "Attendi il completamento dell'installazione corrente."
            )
            return

        core = self.combo_core.currentData()
        proxy_url = None
        if self.chk_proxy.isChecked():
            proxy_url = costruisci_proxy_url(
                self.edit_host.text().strip(),
                self.spin_porta.value(),
                self.edit_user.text().strip() or None,
                self.edit_pass.text() or None,
            )

        args, env_extra = comando_installazione(
            self.arduino_cli,
            core_id=core["id"],
            url_extra=core.get("url_extra"),
            proxy_url=proxy_url,
        )
        programma, argomenti = args[0], args[1:]

        self.console.clear()
        self.console.appendPlainText(f"$ {programma} {' '.join(argomenti)}")
        if proxy_url:
            self.console.appendPlainText(f"Proxy: {proxy_url}")

        self._processo = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        for k, v in env_extra.items():
            env.insert(k, v)
        self._processo.setProcessEnvironment(env)
        self._processo.setProcessChannelMode(QProcess.MergedChannels)
        self._processo.readyReadStandardOutput.connect(self._on_output)
        self._processo.finished.connect(self._on_finished)
        self._processo.errorOccurred.connect(self._on_error)

        self.btn_installa.setEnabled(False)
        self._processo.start(programma, argomenti)

    @Slot()
    def _on_output(self):
        if self._processo is None:
            return
        testo = bytes(self._processo.readAllStandardOutput()).decode("utf-8", errors="replace")
        if testo:
            self.console.moveCursor(QTextCursor.MoveOperation.End)
            self.console.insertPlainText(testo)
            self.console.ensureCursorVisible()

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code, status):
        self.btn_installa.setEnabled(True)
        if exit_code == 0:
            self.console.appendPlainText("\n✅ Installazione completata.")
            self._carica_installati()
            self._installato_qualcosa = True
        else:
            self.console.appendPlainText(f"\n❌ Installazione fallita (codice {exit_code}).")
        self._processo = None

    @Slot(QProcess.ProcessError)
    def _on_error(self, errore):
        self.btn_installa.setEnabled(True)
        self.console.appendPlainText(f"\n❌ Errore di avvio: {errore}")
        self._processo = None

    @property
    def installato_qualcosa(self) -> bool:
        return self._installato_qualcosa
