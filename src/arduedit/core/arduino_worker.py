"""Esecuzione di arduino-cli (compile/upload) in un QProcess separato."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal, Slot

log = logging.getLogger(__name__)


class ArduinoWorker(QObject):
    """Esegue arduino-cli in modo asincrono, emettendo segnali per la UI."""

    started = Signal(str)  # "compile" oppure "upload"
    output = Signal(str)  # testo (già decodificato)
    finished = Signal(str, int)  # (modalità, exit_code)
    annullato = Signal(str)  # (modalità) — annullamento riuscito
    failed_to_start = Signal(str)  # processo non avviato

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._modalita = ""
        self._annullato = False
        self._in_corso = False  # stato esplicito, indipendente da QProcess

    # ------------------------------------------------------------------ API

    def is_running(self) -> bool:
        """Vero dall'emissione di `started` fino a `finished`/`annullato`.

        Non si basa solo su QProcess.state() perché tra `started.emit` e
        `QProcess.start()` c'è una finestra in cui lo stato è NotRunning.
        """
        return self._in_corso or (self._process is not None and self._process.state() != QProcess.NotRunning)

    def compila(self, arduino_cli: Path, progetto: Path, fqbn: str) -> None:
        """Compila soltanto (pulsante 'Verifica')."""
        args = self._args_compile(arduino_cli, progetto, fqbn)
        self._avvia(arduino_cli, args, "compile")

    def compila_e_carica(self, arduino_cli: Path, progetto: Path, fqbn: str, porta: str) -> None:
        """Compila e carica in un solo passaggio (pulsante 'Carica')."""
        args = self._args_compile(arduino_cli, progetto, fqbn)
        args += ["--upload", "--port", porta]
        self._avvia(arduino_cli, args, "upload")

    def annulla(self) -> None:
        """Termina il processo e i suoi figli (avr-gcc, esptool, avrdude)."""
        if not self.is_running() or self._annullato:
            return
        self._annullato = True
        self.output.emit("\n⏹ Annullamento in corso…\n")

        # Se il processo non è ancora partito, _on_process_started lo ucciderà
        # appena Qt emette `started`. Se è già partito, uccidiamo subito.
        pid = self._process.processId() if self._process is not None else 0
        if pid and pid > 0:
            self._taskkill_albero(pid)
            if self.is_running() and self._process is not None:
                self._process.kill()

    # ------------------------------------------------------------- interni

    def _args_compile(self, arduino_cli: Path, progetto: Path, fqbn: str) -> list[str]:
        progetto = Path(progetto)
        lib_dir = progetto / "libraries"
        build_dir = progetto / "build"
        build_dir.mkdir(exist_ok=True)

        args = ["compile", "--fqbn", fqbn, "--build-path", str(build_dir)]
        if lib_dir.is_dir():
            # Rende la cartella del progetto prioritaria per la risoluzione
            args += ["--libraries", str(lib_dir)]
        args.append(str(progetto))
        return args

    def _avvia(self, arduino_cli: Path, args: list[str], modalita: str) -> None:
        if self.is_running():
            self.output.emit("⚠ Operazione già in corso.\n")
            return

        self._modalita = modalita
        self._annullato = False
        self._in_corso = True  # PRIMA di started.emit, così la UI vede True

        self._process = QProcess(self)
        self._process.setProgram(str(arduino_cli))
        self._process.setArguments(args)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.started.connect(self._on_process_started)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self.output.emit(f"$ {arduino_cli} {' '.join(args)}\n")
        self.started.emit(modalita)
        self._process.start()

    def _taskkill_albero(self, pid: int) -> None:
        """Uccide il processo e i suoi discendenti su Windows."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                check=False,
                timeout=5,
                creationflags=flags,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            log.warning("taskkill fallito per PID %s: %s", pid, exc)

    # --------------------------------------------------------------- slot

    @Slot()
    def _on_process_started(self) -> None:
        if self._annullato and self._process is not None:
            pid = self._process.processId()
            if pid and pid > 0:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    check=False,
                    timeout=5,
                )
            if self._process is not None:
                self._process.kill()

    @Slot()
    def _on_output(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.emit(data)

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        modalita = self._modalita
        era_annullato = self._annullato
        self._modalita = ""
        self._annullato = False
        self._in_corso = False
        self._process = None
        if era_annullato:
            self.annullato.emit(modalita)
        else:
            self.finished.emit(modalita, exit_code)

    @Slot(QProcess.ProcessError)
    def _on_error(self, errore: QProcess.ProcessError) -> None:
        msg = f"Impossibile avviare arduino-cli: {errore}"
        log.error(msg)
        self._modalita = ""
        self._annullato = False
        self._in_corso = False
        self._process = None
        self.failed_to_start.emit(msg)
