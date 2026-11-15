# """Rilevamento delle porte seriali con schede Arduino/ESP32 collegate."""

# from __future__ import annotations

# import json
# import logging
# import re
# import subprocess
# from dataclasses import dataclass
# from pathlib import Path

# from PySide6.QtSerialPort import QSerialPortInfo

# log = logging.getLogger(__name__)


# VID_PID_NOTI: dict[int, tuple[int | None, str]] = {
#     0x2341: (None, "Arduino"),
#     0x2A03: (None, "Arduino (legacy)"),
#     0x1A86: (None, "WCH CH340/CH341"),
#     0x10C4: (None, "Silicon Labs CP210x"),
#     0x0403: (None, "FTDI"),
#     0x067B: (None, "Prolific PL2303"),
#     0x303A: (None, "Espressif nativo"),
# }


# @dataclass
# class PortaRilevata:
#     device: str
#     descrizione: str
#     scheda: str | None = None
#     fqbn: str | None = None
#     vid: int | None = None
#     pid: int | None = None
#     chip: str | None = None

#     @property
#     def etichetta(self) -> str:
#         if self.scheda:
#             return f"{self.device} — {self.scheda}"
#         if self.chip:
#             return f"{self.device} — {self.chip}"
#         return f"{self.device} — {self.descrizione}"


# def _chiave_ordinamento(device: str) -> tuple[str, int]:
#     match = re.search(r"(\d+)$", device or "")
#     if not match:
#         return (device or "", 0)
#     return (device[: match.start()], int(match.group(1)))


# def scansiona_porte(
#     arduino_cli: Path | None = None,
#     includi_sconosciute: bool = False,
# ) -> list[PortaRilevata]:
#     """Restituisce le porte seriali, arricchite con i dati di arduino-cli.

#     Non solleva mai eccezioni: in caso di problemi restituisce ciò che
#     è riuscita a rilevare (anche lista vuota).
#     """
#     porte: dict[str, PortaRilevata] = {}

#     try:
#         info_porte = QSerialPortInfo.availablePorts()
#     except Exception:  # noqa: BLE001
#         log.exception("Errore in QSerialPortInfo.availablePorts()")
#         info_porte = []

#     for info in info_porte:
#         try:
#             vid = info.vendorIdentifier() or None
#             pid = info.productIdentifier() or None
#             chip = None
#             if vid is not None:
#                 entry = VID_PID_NOTI.get(vid)
#                 if entry is not None:
#                     atteso_pid, etichetta = entry
#                     if atteso_pid is None or atteso_pid == pid:
#                         chip = etichetta
#             porta = PortaRilevata(
#                 device=info.portName(),
#                 descrizione=info.description() or "",
#                 vid=vid,
#                 pid=pid,
#                 chip=chip,
#             )
#             porte[porta.device] = porta
#         except Exception:  # noqa: BLE001
#             log.exception("Errore nel processare una porta seriale")

#     if arduino_cli is not None and Path(arduino_cli).exists():
#         try:
#             _arricchisci_con_arduino_cli(porte, Path(arduino_cli))
#         except Exception:  # noqa: BLE001
#             log.exception("Errore durante l'arricchimento con arduino-cli")

#     risultato = [p for p in porte.values() if includi_sconosciute or p.scheda or p.chip]
#     return sorted(risultato, key=lambda p: _chiave_ordinamento(p.device))


# def _arricchisci_con_arduino_cli(porte: dict[str, PortaRilevata], arduino_cli: Path) -> None:
#     try:
#         output = subprocess.check_output(
#             [str(arduino_cli), "board", "list", "--format", "json"],
#             text=True,
#             timeout=5,
#             stderr=subprocess.DEVNULL,
#         )
#     except (subprocess.SubprocessError, OSError) as exc:
#         log.warning("arduino-cli board list fallito: %s", exc)
#         return

#     if not output.strip():
#         return

#     try:
#         dati = json.loads(output)
#     except json.JSONDecodeError as exc:
#         log.warning("JSON di arduino-cli non valido: %s", exc)
#         return

#     # --- Parsing difensivo: accetta lista, dict con 'detected_ports', o singolo dict
#     voci: list = []
#     if isinstance(dati, list):
#         voci = dati
#     elif isinstance(dati, dict):
#         # alcune versioni recenti incapsulano in {'detected_ports': [...]}
#         detected = dati.get("detected_ports")
#         if isinstance(detected, list):
#             voci = detected
#         elif "port" in dati:
#             voci = [dati]
#         else:
#             log.debug("Formato JSON arduino-cli non riconosciuto: chiavi=%s", list(dati))
#             return
#     else:
#         log.debug("JSON arduino-cli è %s, non gestito", type(dati).__name__)
#         return

#     for voce in voci:
#         if not isinstance(voce, dict):
#             continue
#         port_info = voce.get("port")
#         if not isinstance(port_info, dict):
#             continue
#         address = port_info.get("address")
#         if not isinstance(address, str) or address not in porte:
#             continue

#         matching = voce.get("matching_boards")
#         if not isinstance(matching, list) or not matching:
#             continue
#         scheda = matching[0]
#         if not isinstance(scheda, dict):
#             continue
#         porte[address].scheda = scheda.get("name")
#         porte[address].fqbn = scheda.get("fqbn")
"""Rilevamento delle porte seriali con schede Arduino/ESP32 collegate.

Usa pyserial (puro Python) invece di QSerialPortInfo per essere sicuro
in un thread worker, senza marshalling Qt sul thread GUI.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
import time

from serial.tools import list_ports

log = logging.getLogger(__name__)


VID_PID_NOTI: dict[int, tuple[int | None, str]] = {
    0x2341: (None, "Arduino"),
    0x2A03: (None, "Arduino (legacy)"),
    0x1A86: (None, "WCH CH340/CH341"),
    0x10C4: (None, "Silicon Labs CP210x"),
    0x0403: (None, "FTDI"),
    0x067B: (None, "Prolific PL2303"),
    0x303A: (None, "Espressif nativo"),
}


import serial


def _porta_viva(device: str, timeout: float = 0.05) -> bool:
    try:
        s = serial.Serial(device, timeout=timeout)
        s.close()
        return True
    except serial.SerialException as exc:
        msg = str(exc).lower()
        # Porta occupata da un altro processo: è vera, non filtrarla
        if "access is denied" in msg or "permission" in msg:
            return True
        return False
    except OSError:
        return False


@dataclass
class PortaRilevata:
    device: str
    descrizione: str
    scheda: str | None = None
    fqbn: str | None = None
    vid: int | None = None
    pid: int | None = None
    chip: str | None = None

    @property
    def etichetta(self) -> str:
        if self.scheda:
            return f"{self.device} — {self.scheda}"
        if self.chip:
            return f"{self.device} — {self.chip}"
        return f"{self.device} — {self.descrizione}"


def _chiave_ordinamento(device: str) -> tuple[str, int]:
    match = re.search(r"(\d+)$", device or "")
    if not match:
        return (device or "", 0)
    return (device[: match.start()], int(match.group(1)))


def scansiona_porte(
    arduino_cli: Path | None = None,
    includi_sconosciute: bool = False,
    verifica_vive: bool = False,
) -> list[PortaRilevata]:
    """Enumerazione veloce delle porte, senza arricchimento arduino-cli."""
    porte: dict[str, PortaRilevata] = {}

    try:
        info_porte = list_ports.comports()
    except Exception:  # noqa: BLE001
        log.exception("Errore in list_ports.comports()")
        info_porte = []

    for info in info_porte:
        try:
            vid = info.vid
            pid = info.pid
            chip = None
            if vid is not None:
                entry = VID_PID_NOTI.get(vid)
                if entry is not None:
                    atteso_pid, etichetta = entry
                    if atteso_pid is None or atteso_pid == pid:
                        chip = etichetta
            porta = PortaRilevata(
                device=info.device,
                descrizione=info.description or "",
                vid=vid,
                pid=pid,
                chip=chip,
            )
            porte[porta.device] = porta
        except Exception:  # noqa: BLE001
            log.exception("Errore nel processare una porta seriale")

    return _filtra_e_ordina(porte, includi_sconosciute)


def arricchisci_porte(
    porte: list[PortaRilevata],
    arduino_cli: Path | None,
    includi_sconosciute: bool = False,
) -> list[PortaRilevata]:
    """Aggiunge scheda/fqbn alle porte, usando arduino-cli. Lento ma in worker."""
    if arduino_cli is None or not Path(arduino_cli).exists():
        return _filtra_e_ordina({p.device: p for p in porte}, includi_sconosciute)

    mappa = {p.device: p for p in porte}

    try:
        output = subprocess.check_output(
            [str(arduino_cli), "board", "list", "--format", "json"],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("arduino-cli board list fallito: %s", exc)
        return _filtra_e_ordina(mappa, includi_sconosciute)

    if not output.strip():
        return _filtra_e_ordina(mappa, includi_sconosciute)

    try:
        dati = json.loads(output)
    except json.JSONDecodeError as exc:
        log.warning("JSON arduino-cli non valido: %s", exc)
        return _filtra_e_ordina(mappa, includi_sconosciute)

    voci: list = []
    if isinstance(dati, list):
        voci = dati
    elif isinstance(dati, dict):
        detected = dati.get("detected_ports")
        if isinstance(detected, list):
            voci = detected
        elif "port" in dati:
            voci = [dati]
        else:
            return _filtra_e_ordina(mappa, includi_sconosciute)
    else:
        return _filtra_e_ordina(mappa, includi_sconosciute)

    for voce in voci:
        if not isinstance(voce, dict):
            continue
        port_info = voce.get("port")
        if not isinstance(port_info, dict):
            continue
        address = port_info.get("address")
        if not isinstance(address, str) or address not in mappa:
            continue
        matching = voce.get("matching_boards")
        if not isinstance(matching, list) or not matching:
            continue
        scheda = matching[0]
        if not isinstance(scheda, dict):
            continue
        mappa[address].scheda = scheda.get("name")
        mappa[address].fqbn = scheda.get("fqbn")

    return _filtra_e_ordina(mappa, includi_sconosciute)


def _filtra_e_ordina(mappa: dict[str, PortaRilevata], includi_sconosciute: bool) -> list[PortaRilevata]:
    risultato = [p for p in mappa.values() if includi_sconosciute or p.scheda or p.chip]
    return sorted(risultato, key=lambda p: _chiave_ordinamento(p.device))
