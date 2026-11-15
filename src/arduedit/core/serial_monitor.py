"""Monitor seriale delegato ad arduino-cli monitor (sottoprocesso QProcess)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal, Slot

log = logging.getLogger(__name__)


@dataclass
class RigaSeriale:
    testo: str
    timestamp: datetime


class SerialMonitorProcess(QObject):
    riga_ricevuta = Signal(str)
    aperto = Signal(str, int)
    chiuso = Signal()
    errore = Signal(str)

    def __init__(self, arduino_cli: Path | None, parent=None):
        super().__init__(parent)
        self._cli = arduino_cli
        self._process: QProcess | None = None
        self._buffer = bytearray()
        self._porta = ""
        self._baud = 9600

    def apri(self, porta: str, baud: int = 9600) -> None:
        if self._cli is None:
            self.errore.emit("arduino-cli non disponibile.")
            return
        self.chiudi()
        self._porta = porta
        self._baud = baud
        self._buffer.clear()

        self._process = QProcess(self)
        self._process.setProgram(str(self._cli))
        self._process.setArguments(
            [
                "monitor",
                "-p",
                porta,
                "--config",
                f"baudrate={baud}",
                # Su ESP32-S3 il toggle DTR/RTS resetta la scheda: lo disabilitiamo
                "--config",
                "dtr=off",
                "--config",
                "rts=off",
            ]
        )
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.start()
        self.aperto.emit(porta, baud)

    def chiudi(self) -> None:
        if self._process is not None:
            self._process.terminate()
            if not self._process.waitForFinished(1500):
                self._process.kill()
                self._process.waitForFinished(500)
            self._process = None
        self._buffer.clear()

    def is_open(self) -> bool:
        return self._process is not None and self._process.state() != QProcess.NotRunning

    @property
    def porta(self) -> str:
        return self._porta

    @Slot()
    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput())
        if not data:
            return
        self._buffer.extend(data)
        while b"\n" in self._buffer:
            idx = self._buffer.index(0x0A)
            riga = self._buffer[:idx].decode("utf-8", errors="replace").rstrip("\r")
            del self._buffer[: idx + 1]
            if riga:
                self.riga_ricevuta.emit(riga)

    @Slot()
    def _on_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        for linea in data.splitlines():
            if linea.strip():
                log.info("arduino-cli monitor: %s", linea)
                if any(k in linea.lower() for k in ("error", "failed", "cannot", "denied")):
                    self.errore.emit(linea)

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        self._process = None
        self.chiuso.emit()

    @Slot(QProcess.ProcessError)
    def _on_error(self, err: QProcess.ProcessError) -> None:
        self.errore.emit(f"Errore nel monitor: {err}")
