# """Scansione asincrona delle porte seriali."""

# from __future__ import annotations

# import logging
# from pathlib import Path

# from PySide6.QtCore import QObject, QRunnable, Signal

# from arduedit.core.port_discovery import PortaRilevata, scansiona_porte

# log = logging.getLogger(__name__)


# class _SegnaliPorte(QObject):
#     completato = Signal(list)  # list[PortaRilevata]
#     errore = Signal(str)


# class PortScanTask(QRunnable):
#     """Task eseguibile in QThreadPool: non blocca la GUI."""

#     def __init__(self, arduino_cli: Path | None):
#         super().__init__()
#         self.arduino_cli = arduino_cli
#         self.segnali = _SegnaliPorte()

#     def run(self) -> None:  # eseguito in un thread del pool
#         try:
#             porte = scansiona_porte(arduino_cli=self.arduino_cli)
#             self.segnali.completato.emit(porte)
#         except Exception as exc:  # noqa: BLE001
#             log.exception("Errore nella scansione porte")
#             self.segnali.errore.emit(str(exc))
"""Scansione porte in due fasi: veloce su GUI, lenta su worker."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from arduedit.core.port_discovery import (
    PortaRilevata,
    arricchisci_porte,
    scansiona_porte,
)

log = logging.getLogger(__name__)


class _SegnaliPorte(QObject):
    completato = Signal(list)  # list[PortaRilevata]
    errore = Signal(str)


class PortEnrichTask(QRunnable):
    """Arricchisce le porte con arduino-cli. Eseguito in thread pool."""

    def __init__(self, porte_base: list[PortaRilevata], arduino_cli: Path | None):
        super().__init__()
        self.porte_base = porte_base
        self.arduino_cli = arduino_cli
        self.segnali = _SegnaliPorte()

    def run(self) -> None:
        try:
            porte = arricchisci_porte(self.porte_base, self.arduino_cli)
            self.segnali.completato.emit(porte)
        except Exception as exc:  # noqa: BLE001
            log.exception("Errore nell'arricchimento porte")
            self.segnali.errore.emit(str(exc))


def scan_veloce() -> list[PortaRilevata]:
    """Fase 1: enumerazione veloce, chiamabile dal thread GUI."""
    return scansiona_porte(arduino_cli=None)
