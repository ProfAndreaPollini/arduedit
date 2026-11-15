import logging
import shutil
import time
from pathlib import Path

from PySide6.QtCore import QRegularExpression, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolBar,
)

from arduedit.core.arduino_worker import ArduinoWorker
from arduedit.core.boards import _core_fqbn, lista_schede_disponibili
from arduedit.core.paths import trova_arduino_cli
from arduedit.core.port_discovery import scansiona_porte
from arduedit.core.project import Progetto, apri_progetto, crea_progetto
from arduedit.core.project_libraries import librerie_mancanti_da_errore, scarica_libreria_in_progetto
from arduedit.core.settings import _salva_scheda_predefinita, _scheda_predefinita
from arduedit.ui.arduino_completer import ArduinoCompleter
from arduedit.ui.libraries_dialog import LibrerieDialog
from arduedit.ui.library_search_dialog import LibrarySearchDialog
from arduedit.ui.serial_panel import SerialPanel
from arduedit.ui.toolchain_dialog import ToolchainDialog
from arduedit.ui.welcome_page import WelcomePage

# (nome visualizzato, FQBN) — popola la combo "Scheda"
SCHEDE_DISPONIBILI: list[tuple[str, str]] = [
    ("Arduino Uno", "arduino:avr:uno"),
    ("Arduino Nano", "arduino:avr:nano"),
    ("Arduino Nano (Old Bootloader)", "arduino:avr:nano:cpu=atmega328old"),
]

log = logging.getLogger(__name__)


from PySide6.QtCore import QStandardPaths


def _cartella_iniziale() -> str:
    """Percorso iniziale sensato per i file dialog."""
    for tipo in (QStandardPaths.DocumentsLocation, QStandardPaths.HomeLocation):  # type: ignore
        p = QStandardPaths.writableLocation(tipo)
        if p:
            return p
    return str(Path.home())


class ArduinoHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#0000FF"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "\\bsetup\\b",
            "\\bloop\\b",
            "\\bif\\b",
            "\\belse\\b",
            "\\bfor\\b",
            "\\bwhile\\b",
            "\\bint\\b",
            "\\bvoid\\b",
            "\\bboolean\\b",
            "\\bpinMode\\b",
            "\\bdigitalWrite\\b",
            "\\bdigitalRead\\b",
            "\\banalogRead\\b",
            "\\banalogWrite\\b",
            "\\bdelay\\b",
        ]
        for word in keywords:
            self.rules.append((QRegularExpression(word), keyword_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#008000"))
        self.rules.append((QRegularExpression("//[^\n]*"), comment_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#A31515"))
        self.rules.append((QRegularExpression('"[^"]*"'), string_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class MainWindow(QMainWindow):
    def __init__(self, arduino_cli_path: Path | None = None):
        super().__init__()
        self.setWindowTitle("ArduEdit")
        self.setMinimumSize(1024, 600)

        # Risoluzione del percorso di arduino-cli (può essere None se non trovato)
        self.arduino_cli_path: Path | None = arduino_cli_path or trova_arduino_cli()

        print(f"DEBUG: Arduino CLI path: {self.arduino_cli_path}")

        # Progetto corrente (None = nessun progetto aperto)
        self.progetto: Progetto | None = None

        # --- Toolbar ---
        toolbar = QToolBar("Principale")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.combo_scheda = QComboBox()
        self.combo_scheda.setMinimumWidth(280)

        self.combo_porta = QComboBox()
        self.combo_porta.setMinimumWidth(220)

        # Pulsante di aggiornamento porte, accanto alla combo
        self.btn_aggiorna_porte = QPushButton("⟳")
        self.btn_aggiorna_porte.setToolTip("Aggiorna l'elenco delle porte seriali")
        self.btn_aggiorna_porte.setFixedWidth(32)
        self.btn_aggiorna_porte.clicked.connect(self.aggiorna_porte)

        toolbar.addWidget(QLabel(" Scheda: "))
        toolbar.addWidget(self.combo_scheda)
        toolbar.addWidget(QLabel("  Porta: "))
        toolbar.addWidget(self.combo_porta)
        toolbar.addWidget(self.btn_aggiorna_porte)
        toolbar.addSeparator()

        self.btn_verifica = QPushButton("✓ Verifica")
        self.btn_carica = QPushButton("▶ Carica")
        self.btn_carica.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 6px 14px;")

        self.btn_monitor = QPushButton("📡 Monitor")
        self.btn_librerie = QPushButton("📚 Librerie")
        self.btn_verifica.clicked.connect(self.verifica)
        self.btn_carica.clicked.connect(self.carica)
        self.btn_librerie.clicked.connect(self._apri_librerie)
        self.btn_monitor.clicked.connect(self._toggle_monitor)
        for b in (self.btn_verifica, self.btn_carica, self.btn_monitor, self.btn_librerie):
            toolbar.addWidget(b)

        self.btn_annulla = QPushButton("⏹ Annulla")
        self.btn_annulla.setStyleSheet("background-color: #c62828; color: white; padding: 6px 14px;")
        self.btn_annulla.setVisible(False)
        self.btn_annulla.clicked.connect(self._on_click_annulla)
        toolbar.addWidget(self.btn_annulla)

        # Worker
        self.worker = ArduinoWorker(self)
        self.worker.started.connect(self._on_worker_started)
        self.worker.output.connect(self._on_worker_output)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.failed_to_start.connect(self._on_worker_failed)
        self.worker.annullato.connect(self._on_worker_annullato)

        # --- Editor ---
        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("font-family: Consolas, monospace; font-size: 16pt;")
        self.highlighter = ArduinoHighlighter(self.editor.document())
        self.completer = ArduinoCompleter(self.editor)

        # --- Pannello inferiore ---
        self.tabs = QTabWidget()
        self.console = QPlainTextEdit(readOnly=True)
        # self.seriale = QPlainTextEdit(readOnly=True)
        self.seriale = SerialPanel(self.arduino_cli_path)

        self.tabs.addTab(self.console, "Console")
        self.tabs.addTab(self.seriale, "Monitor Seriale")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.tabs)
        splitter.setSizes([500, 200])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, True)
        self.setCentralWidget(splitter)

        # --- Status bar ---
        sb = QStatusBar()
        self.lbl_pos = QLabel("Riga 1, Col 1")
        self.lbl_stato = QLabel("✅ Pronto")
        sb.addWidget(self.lbl_pos)
        sb.addPermanentWidget(self.lbl_stato)
        self.setStatusBar(sb)

        # Segnali
        self.editor.cursorPositionChanged.connect(self._aggiorna_posizione)
        self.combo_porta.currentIndexChanged.connect(self._on_porta_changed)

        # Popolamento iniziale
        if self.arduino_cli_path is None:
            self._log_console(
                "⚠ arduino-cli non trovato: compilazione e upload non saranno disponibili.",
                errore=True,
            )
        # self.aggiorna_porte()

        self.recenti: list[Path] = self._carica_recenti()

        # Stack: welcome page <-> editor
        self.welcome = WelcomePage()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(splitter)
        self.stack.setCurrentWidget(self.welcome)
        self.setCentralWidget(self.stack)

        self.welcome.nuovo_progetto_richiesto.connect(self.nuovo_progetto)
        self.welcome.apri_progetto_richiesto.connect(self.apri_progetto)
        self.welcome.progetto_recente_scelto.connect(self.carica_progetto)

        # Menu File
        self._costruisci_menu_file()
        QTimer.singleShot(50, self.aggiorna_porte)

        menu_strumenti = self.menuBar().addMenu("&Strumenti")
        menu_strumenti.addAction("Gestione toolchain…", self._apri_toolchain)

        # Altro setup toolbar/status bar come prima
        self._aggiorna_titolo()
        # self.aggiorna_porte()
        # Carica le schede all'avvio (veloce, sincrono)
        self._carica_schede()
        self._aggiorna_stato_azioni()

    def _on_click_annulla(self):
        self.btn_annulla.setEnabled(False)
        self.worker.annulla()

    @Slot(str)
    def _on_worker_annullato(self, modalita: str):
        if modalita == "compile" and self.progetto is not None:
            build = self.progetto.cartella / "build"
            if build.exists():
                try:
                    shutil.rmtree(build)
                    self._log_console("ℹ Cartella build ripulita dopo annullamento.")
                except OSError:
                    pass

        self.lbl_stato.setText("⏹ Operazione annullata")
        self.console.appendPlainText(f"\n⏹ {'Compilazione' if modalita == 'compile' else 'Caricamento'} annullato.\n")
        # Se stavi per riaprire il monitor, non riaprirlo dopo un annullamento
        self._monitor_da_riaprire = False
        self._aggiorna_stato_azioni()

    def _attendi_porta_disponibile(self, porta: str, timeout: float = 5.0) -> bool:
        """Attende che una porta compaia nell'elenco di Windows."""
        from serial.tools import list_ports

        inizio = time.monotonic()
        while time.monotonic() - inizio < timeout:
            if any(p.device == porta for p in list_ports.comports()):
                return True
            time.sleep(0.2)
        return False

    def _toggle_monitor(self):
        if self.seriale.is_open():
            self.seriale.chiudi()
            self.btn_monitor.setText("📡 Monitor")
            return
        porta = self.combo_porta.currentData()
        if not porta:
            QMessageBox.information(self, "Nessuna porta", "Seleziona una porta seriale.")
            return
        if not self._attendi_porta_disponibile(porta, timeout=2.0):
            self.aggiorna_porte()  # riscopre le porte
            porta = self.combo_porta.currentData()
            if not porta:
                QMessageBox.information(
                    self,
                    "Nessuna porta",
                    "La scheda non è stata rilevata. Controlla il cavo USB e premi ⟳ per aggiornare le porte.",
                )
                return
        self.seriale.apri(porta)
        self.btn_monitor.setText("⏹ Chiudi monitor")
        self.tabs.setCurrentWidget(self.seriale)

    def _apri_toolchain(self):
        if self.arduino_cli_path is None:
            QMessageBox.warning(
                self, "arduino-cli assente", "arduino-cli non è stato trovato. Controlla la configurazione."
            )
            return
        dlg = ToolchainDialog(self.arduino_cli_path, self)
        dlg.exec()
        if dlg.installato_qualcosa:
            self._carica_schede()
            self._log_console("🔄 Elenco schede aggiornato dopo installazione toolchain.")

    def _aggiorna_stato_azioni(self):
        """Abilita/disabilita i pulsanti in base allo stato dell'app."""
        worker = getattr(self, "worker", None)
        progetto_aperto = self.progetto is not None
        worker_occupato = worker.is_running()
        puo_agire = progetto_aperto and not worker_occupato and self.arduino_cli_path is not None

        self.btn_verifica.setEnabled(puo_agire)
        self.btn_carica.setEnabled(puo_agire and bool(self.combo_porta.currentData()))
        self.btn_librerie.setEnabled(progetto_aperto and not worker_occupato)
        self.btn_monitor.setEnabled(progetto_aperto and not worker_occupato)

        # Porta e scheda restano modificabili anche senza progetto? No:
        # senza progetto non ha senso cambiarle, e riduce la confusione.
        self.combo_scheda.setEnabled(progetto_aperto and not worker_occupato)
        self.combo_porta.setEnabled(progetto_aperto and not worker_occupato)
        self.btn_aggiorna_porte.setEnabled(progetto_aperto and not worker_occupato)

        # Annulla visibile solo durante un'operazione
        if worker_occupato:
            self.btn_carica.setVisible(False)
            self.btn_annulla.setVisible(True)
            self.btn_annulla.setEnabled(True)
        else:
            self.btn_annulla.setVisible(False)
            self.btn_carica.setVisible(True)
            self.btn_carica.setEnabled(puo_agire and bool(self.combo_porta.currentData()))

    def _carica_schede(self):
        """Popola la combo schede dai core installati."""
        corrente = self.combo_scheda.currentData()
        self.combo_scheda.blockSignals(True)
        self.combo_scheda.clear()

        if self.arduino_cli_path is None:
            self.combo_scheda.addItem("arduino-cli non trovato", userData=None)
            self.combo_scheda.setEnabled(False)
            self.combo_scheda.blockSignals(False)
            return

        schede = lista_schede_disponibili(self.arduino_cli_path)

        if not schede:
            self.combo_scheda.addItem(
                "Nessuna scheda disponibile — installa una toolchain",
                userData=None,
            )
            self.combo_scheda.setEnabled(False)
            self.combo_scheda.blockSignals(False)
            return

        # Raggruppa per piattaforma come separatori visivi
        piattaforma_corrente = None
        for s in schede:
            if s.piattaforma != piattaforma_corrente:
                # Separatore non selezionabile
                self.combo_scheda.insertSeparator(self.combo_scheda.count())
                piattaforma_corrente = s.piattaforma
            self.combo_scheda.addItem(s.etichetta, userData=s.fqbn)

        self.combo_scheda.setEnabled(True)

        # Ripristina la selezione precedente, se ancora presente
        if corrente:
            idx = self.combo_scheda.findData(corrente)
            if idx >= 0:
                self.combo_scheda.setCurrentIndex(idx)

        fqbn_target = corrente or _scheda_predefinita()
        if fqbn_target:
            idx = self.combo_scheda.findData(fqbn_target)
            if idx >= 0:
                self.combo_scheda.setCurrentIndex(idx)

        self.combo_scheda.blockSignals(False)
        self._on_scheda_changed(self.combo_scheda.currentIndex())

    def _on_scheda_changed(self, index: int):
        if index < 0:
            return
        fqbn = self.combo_scheda.currentData()
        if fqbn:
            _salva_scheda_predefinita(fqbn)
        self._aggiorna_stato_azioni()
        self._avvisa_se_scheda_diversa()

    # --------------------------------------------------------------- menu

    def _costruisci_menu_file(self):
        menu = self.menuBar().addMenu("&File")
        menu.addAction("Nuovo progetto…", self.nuovo_progetto, "Ctrl+N")
        menu.addAction("Apri progetto…", self.apri_progetto, "Ctrl+O")
        self.menu_recenti = menu.addMenu("Progetti recenti")
        self._aggiorna_menu_recenti()
        menu.addSeparator()
        menu.addAction("Salva", self.salva, "Ctrl+S")
        menu.addAction("Chiudi progetto", self.chiudi_progetto)

    def _aggiorna_menu_recenti(self):
        self.menu_recenti.clear()
        if not self.recenti:
            az = self.menu_recenti.addAction("(nessuno)")
            az.setEnabled(False)
            return
        for p in self.recenti:
            self.menu_recenti.addAction(
                f"{p.name} — {p}",
                lambda checked=False, percorso=p: self.carica_progetto(percorso),
            )

    def _apri_librerie(self):
        if self.progetto is None:
            QMessageBox.information(
                self, "Nessun progetto aperto", "Apri o crea un progetto prima di gestire le librerie."
            )
            return
        dlg = LibrerieDialog(self.progetto.cartella, self)
        dlg.ricerca_online_richiesta.connect(lambda: self._apri_ricerca_libreria(dlg))

        dlg.exec()

    def _apri_ricerca_libreria(self, dlg_librerie: LibrerieDialog):
        if self.arduino_cli_path is None:
            QMessageBox.warning(self, "arduino-cli assente", "Impossibile cercare librerie senza arduino-cli.")
            return
        search = LibrarySearchDialog(self.arduino_cli_path, self)

        def on_scelta(nome: str):
            self._installa_libreria_da_indice(nome, dlg_librerie)

        search.libreria_scelta.connect(on_scelta)
        search.exec()

    def _installa_libreria_da_indice(self, nome: str, dlg_librerie: LibrerieDialog):
        self._log_console(f"📦 Download di '{nome}'…")
        try:
            dest = scarica_libreria_in_progetto(self.arduino_cli_path, nome, self.progetto.cartella)
        except (OSError, ValueError, RuntimeError) as exc:
            self._log_console(f"❌ Installazione fallita: {exc}", errore=True)
            QMessageBox.warning(dlg_librerie, "Installazione fallita", str(exc))
            return
        self._log_console(f"✅ Libreria installata in {dest}")
        dlg_librerie.aggiorna()

    # --------------------------------------------------------------- azioni

    def nuovo_progetto(self):
        if not self._conferma_abbandono():
            return
        nome, ok = QInputDialog.getText(
            self,
            "Nuovo progetto",
            "Nome del progetto:",
            text="NuovoProgetto",
        )
        if not ok or not nome.strip():
            return
        genitore = QFileDialog.getExistingDirectory(
            self,
            "Dove vuoi creare il progetto?",
            _cartella_iniziale(),
        )
        if not genitore:
            return
        cartella = Path(genitore) / nome.strip()
        try:
            progetto = crea_progetto(cartella)
        except ValueError as exc:
            QMessageBox.warning(self, "Impossibile creare il progetto", str(exc))
            return
        self._apri_nel_progetto(progetto)

    def apri_progetto(self):
        if not self._conferma_abbandono():
            return
        cartella = QFileDialog.getExistingDirectory(
            self,
            "Scegli la cartella del progetto",
            _cartella_iniziale(),
        )
        if not cartella:
            return
        try:
            progetto = apri_progetto(Path(cartella))
        except ValueError as exc:
            QMessageBox.warning(self, "Cartella non valida", str(exc))
            return
        self._apri_nel_progetto(progetto)

    def carica_progetto(self, cartella: Path):
        if not self._conferma_abbandono():
            return
        try:
            progetto = apri_progetto(Path(cartella))
        except ValueError as exc:
            QMessageBox.warning(
                self,
                "Progetto non disponibile",
                f"Impossibile aprire '{cartella}':\n{exc}",
            )
            self._rimuovi_recente(Path(cartella))
            return
        self._apri_nel_progetto(progetto)

    def salva(self):
        if self.progetto is None:
            return
        try:
            self.progetto.scrivi(self.editor.toPlainText())
            self.editor.document().setModified(False)
            self._log_console(f"💾 Salvato: {self.progetto.file_principale.name}")
        except OSError as exc:
            QMessageBox.critical(self, "Errore di salvataggio", str(exc))

    def chiudi_progetto(self):
        if not self._conferma_abbandono():
            return
        self.progetto = None
        self._aggiorna_stato_azioni()
        self.editor.clear()
        self.editor.document().setModified(False)
        self.stack.setCurrentWidget(self.welcome)
        self._aggiorna_titolo()

    # --------------------------------------------------------------- helper

    def _apri_nel_progetto(self, progetto: Progetto):
        try:
            testo = progetto.leggi()
        except OSError as exc:
            QMessageBox.critical(self, "Errore di lettura", str(exc))
            return
        self.progetto = progetto
        self._aggiorna_stato_azioni()
        self.editor.setPlainText(testo)
        self.editor.document().setModified(False)
        self.editor.setFocus()
        self.stack.setCurrentWidget(self.editor.parent())  # il splitter
        self._aggiungi_recente(progetto.cartella)
        self._aggiorna_titolo()
        self._log_console(f"📂 Progetto aperto: {progetto.cartella}")

    def _conferma_abbandono(self) -> bool:
        """True se si può procedere, False se l'utente annulla."""
        if self.progetto is None or not self.editor.document().isModified():
            return True
        r = QMessageBox.question(
            self,
            "Modifiche non salvate",
            "Il progetto ha modifiche non salvate. Vuoi salvarle?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if r == QMessageBox.Save:
            self.salva()
            return True
        return r == QMessageBox.Discard

    def _aggiorna_titolo(self):
        if self.progetto is None:
            self.setWindowTitle("ArduEdit")
        else:
            modificato = " *" if self.editor.document().isModified() else ""
            self.setWindowTitle(f"{self.progetto.nome}{modificato} — ArduEdit")

    # --------------------------------------------------------------- recenti

    def _carica_recenti(self) -> list[Path]:
        s = QSettings("Scuola", "ArduEdit")
        raw = s.value("progetti_recenti", [])
        if isinstance(raw, str):
            raw = [raw]
        return [Path(p) for p in (raw or []) if Path(p).is_dir()][:10]

    def _aggiungi_recente(self, percorso: Path):
        percorso = Path(percorso).resolve()
        self.recenti = [percorso] + [p for p in self.recenti if p.resolve() != percorso]
        self.recenti = self.recenti[:10]
        QSettings("Scuola", "ArduEdit").setValue("progetti_recenti", [str(p) for p in self.recenti])
        self.welcome.set_recenti(self.recenti)
        self._aggiorna_menu_recenti()

    def _rimuovi_recente(self, percorso: Path):
        self.recenti = [p for p in self.recenti if p != Path(percorso)]
        QSettings("Scuola", "ArduEdit").setValue("progetti_recenti", [str(p) for p in self.recenti])
        self.welcome.set_recenti(self.recenti)
        self._aggiorna_menu_recenti()

    # --------------------------------------------------------------- close

    def closeEvent(self, event):
        if self._conferma_abbandono():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------ helpers

    def _aggiorna_posizione(self):
        cur = self.editor.textCursor()
        self.lbl_pos.setText(f"Riga {cur.blockNumber() + 1}, Col {cur.positionInBlock() + 1}")

    def _log_console(self, testo: str, errore: bool = False):
        if errore:
            self.console.appendHtml(f'<span style="color: #c62828;">{testo}</span>')
        else:
            self.console.appendPlainText(testo)

    # ------------------------------------------------------------------ porte

    def aggiorna_porte(self):
        """Ripopola la combo delle porte. Non solleva mai eccezioni."""
        try:
            corrente = self.combo_porta.currentData()
            self.combo_porta.blockSignals(True)
            self.combo_porta.clear()

            porte = scansiona_porte(arduino_cli=self.arduino_cli_path, verifica_vive=True)

            for p in porte:
                self.combo_porta.addItem(p.etichetta, userData=p.device)
                self.combo_porta.setItemData(self.combo_porta.count() - 1, p, Qt.ItemDataRole.UserRole + 1)

            if not porte:
                self.combo_porta.addItem("Nessuna scheda rilevata", userData=None)
                self.combo_porta.setEnabled(False)
            else:
                self.combo_porta.setEnabled(True)
                if corrente:
                    idx = self.combo_porta.findData(corrente)
                    if idx >= 0:
                        self.combo_porta.setCurrentIndex(idx)
        except Exception:  # noqa: BLE001
            log.exception("Errore in aggiorna_porte")
            self.combo_porta.clear()
            self.combo_porta.addItem("Errore nel rilevamento porte", userData=None)
            self.combo_porta.setEnabled(False)
            self._log_console("⚠ Errore nel rilevamento porte (vedi log).", errore=True)
        finally:
            self.combo_porta.blockSignals(False)
            try:
                self._on_porta_changed(self.combo_porta.currentIndex())
            except Exception:  # noqa: BLE001
                log.exception("Errore in _on_porta_changed")

    def _on_porta_changed(self, index: int):
        """Auto-seleziona la scheda (FQBN) in base alla porta rilevata."""
        if index < 0:
            return
        porta = self.combo_porta.itemData(index, Qt.UserRole + 1)
        if porta is None or getattr(porta, "fqbn", None) is None:
            return
        idx = self.combo_scheda.findData(porta.fqbn)
        if idx >= 0:
            self.combo_scheda.setCurrentIndex(idx)
        self._aggiorna_stato_azioni()
        self._avvisa_se_scheda_diversa()
        # ------------------------------------------------------------- azioni

    def verifica(self):
        if not self._pronto_per_compilare():
            return
        self.salva_senza_prompt()
        fqbn = self.combo_scheda.currentData()
        self.worker.compila(self.arduino_cli_path, self.progetto.cartella, fqbn)

    def _verifica_corrispondenza_scheda(self) -> tuple[bool, str]:
        """Confronta la scheda fisica rilevata con quella selezionata.

        Restituisce (ok, messaggio).
        - ok=True e messaggio="" quando non ci sono elementi per decidere
        (porta non selezionata, scheda fisica non identificata) o quando
        la corrispondenza è confermata.
        - ok=False e messaggio valorizzato quando c'è una discrepanza.
        """
        idx = self.combo_porta.currentIndex()
        if idx < 0:
            return True, ""
        porta = self.combo_porta.itemData(idx, Qt.ItemDataRole.UserRole + 1)
        if porta is None or not getattr(porta, "fqbn", None):
            # Scheda fisica non identificata: nessun avviso, per non generare rumore
            return True, ""

        fqbn_fisico = _core_fqbn(porta.fqbn)
        fqbn_selezionato = _core_fqbn(self.combo_scheda.currentData())

        if not fqbn_selezionato or fqbn_fisico == fqbn_selezionato:
            return True, ""

        nome_fisico = getattr(porta, "scheda", None) or fqbn_fisico
        nome_selezionato = self.combo_scheda.currentText() or fqbn_selezionato
        return False, (
            f"⚠ La scheda collegata su {porta.device} sembra essere "
            f'"{nome_fisico}", ma è selezionato "{nome_selezionato}".\n'
            f"   Controlla la selezione della scheda prima di caricare.\n"
        )

    def _avvisa_se_scheda_diversa(self):
        ok, messaggio = self._verifica_corrispondenza_scheda()
        if not ok:
            self._log_console(messaggio, errore=True)

    def carica(self):
        if not self._pronto_per_compilare():
            return
        porta = self.combo_porta.currentData()
        if not porta:
            QMessageBox.information(self, "Nessuna porta", "Seleziona la porta seriale della scheda.")
            return

        ok, messaggio = self._verifica_corrispondenza_scheda()
        if not ok:
            risposta = QMessageBox.warning(
                self,
                "Scheda selezionata diversa da quella collegata",
                messaggio + "\nVuoi caricare comunque?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,  # default: No
            )
            if risposta != QMessageBox.Yes:
                return

        self.salva_senza_prompt()
        # Qui, quando implementerai il monitor seriale, chiuderai la porta:
        # self._chiudi_monitor_seriale()
        fqbn = self.combo_scheda.currentData()
        self.worker.compila_e_carica(self.arduino_cli_path, self.progetto.cartella, fqbn, porta)

    # ------------------------------------------------------------- worker

    @Slot(str)
    def _on_worker_started(self, modalita: str):
        self.tabs.setCurrentWidget(self.console)
        self.console.appendPlainText("")
        self._abilita_azioni(False)
        self.lbl_stato.setText("⏳ Compilazione…" if modalita == "compile" else "⏳ Caricamento…")
        self._aggiorna_stato_azioni()

    @Slot(str)
    def _on_worker_output(self, testo: str):
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(testo)
        self.console.ensureCursorVisible()

    @Slot(str, int)
    def _on_worker_finished(self, modalita: str, exit_code: int):
        self._abilita_azioni(True)

        if exit_code == 0:
            msg = "✅ Compilazione riuscita." if modalita == "compile" else "✅ Sketch caricato sulla scheda."
            self.lbl_stato.setText(msg)
            self.console.appendPlainText(f"\n{msg}\n")
        else:
            self.lbl_stato.setText(f"❌ Errore (codice {exit_code})")
            self.console.appendPlainText(f"\n❌ Operazione fallita (codice {exit_code}).\n")
        self._aggiorna_stato_azioni()
        if exit_code != 0:
            # Analizza l'output accumulato nella console (o meglio: nel worker)
            testo = self.console.toPlainText()
            mancanti = librerie_mancanti_da_errore(testo)
            if mancanti:
                nomi = ", ".join(mancanti)
                risposta = QMessageBox.question(
                    self,
                    "Libreria mancante",
                    f"La libreria '{nomi}' non è installata in questo progetto.\n"
                    "Vuoi aprire il pannello Librerie per aggiungerla?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if risposta == QMessageBox.Yes:
                    self._apri_librerie()

    @Slot(str)
    def _on_worker_failed(self, msg: str):
        self._abilita_azioni(True)
        self._aggiorna_stato_azioni()
        self.lbl_stato.setText("❌ Errore")
        self.console.appendPlainText(f"\n{msg}\n")
        QMessageBox.critical(self, "Errore", msg)

    # ------------------------------------------------------------- helper

    def _pronto_per_compilare(self) -> bool:
        if self.progetto is None:
            QMessageBox.information(self, "Nessun progetto aperto", "Apri o crea un progetto prima di compilare.")
            return False
        if self.arduino_cli_path is None:
            QMessageBox.warning(self, "arduino-cli non trovato", "Impossibile compilare senza arduino-cli.")
            return False
        if not self.combo_scheda.currentData():
            QMessageBox.information(self, "Nessuna scheda", "Seleziona la scheda prima di compilare.")
            return False
        if self.worker.is_running():
            return False
        return True

    def _abilita_azioni(self, abilitati: bool):
        for w in (
            self.btn_verifica,
            self.btn_carica,
            self.btn_aggiorna_porte,
            self.combo_porta,
            self.combo_scheda,
        ):
            w.setEnabled(abilitati)

    def salva_senza_prompt(self):
        """Salva silenziosamente se ci sono modifiche non salvate."""
        if self.progetto is None or not self.editor.document().isModified():
            return
        try:
            self.progetto.scrivi(self.editor.toPlainText())
            self.editor.document().setModified(False)
            self._aggiorna_titolo()
        except OSError as exc:
            self._log_console(f"⚠ Impossibile salvare: {exc}", errore=True)
