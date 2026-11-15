"""Riconoscimento e installazione delle toolchain (core) di Arduino."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)


# Core "consigliati" per la scuola, con gli URL aggiuntivi necessari.
# L'insegnante può installarli con un click senza dover ricordare gli URL.
CORE_CONSIGLIATI: list[dict] = [
    {
        "id": "arduino:avr",
        "nome": "Arduino AVR (Uno, Nano, Mega)",
        "url_extra": None,
    },
    {
        "id": "esp32:esp32",
        "nome": "ESP32 (DevKit, WROOM, S3, C3)",
        "url_extra": "https://espressif.github.io/arduino-esp32/package_esp32_index.json",
    },
    {
        "id": "esp8266:esp8266",
        "nome": "ESP8266 (NodeMCU, Wemos D1)",
        "url_extra": "https://arduino.esp8266.com/stable/package_esp8266com_index.json",
    },
    {
        "id": "arduino:samd",
        "nome": "Arduino SAMD (MKR, Zero)",
        "url_extra": None,
    },
]


@dataclass
class CoreInfo:
    id: str  # es. "arduino:avr"
    installed_version: str | None  # None se non installato
    latest_version: str | None
    nome: str | None = None  # nome leggibile, se disponibile

    @property
    def installato(self) -> bool:
        return self.installed_version is not None

    @property
    def aggiornabile(self) -> bool:
        return (
            self.installed_version is not None
            and self.latest_version is not None
            and self.installed_version != self.latest_version
        )


def lista_core_installati(arduino_cli: Path) -> list[CoreInfo]:
    """Elenca i core effettivamente installati nella data directory."""
    try:
        output = subprocess.check_output(
            [str(arduino_cli), "core", "list", "--format", "json"],
            text=True,
            timeout=15,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("core list fallito: %s", exc)
        return []

    if not output.strip():
        return []

    try:
        dati = json.loads(output)
    except json.JSONDecodeError:
        log.warning("JSON di core list non valido")
        return []

    # Formato atteso: {"platforms": [{"id": "...", "installed_version": "...", ...}]}
    # Alcune versioni restituiscono una lista piatta, o null se non c'è nulla.
    if dati is None:
        return []
    if isinstance(dati, list):
        voci = dati
    elif isinstance(dati, dict):
        voci = dati.get("platforms", [])
    else:
        return []

    risultato: list[CoreInfo] = []
    for voce in voci:
        if not isinstance(voce, dict):
            continue
        # I campi sono cambiati tra versioni: id/ID, installed_version/Installed/installed
        core_id = voce.get("id") or voce.get("ID")
        installed = voce.get("installed_version") or voce.get("Installed") or voce.get("installed")
        latest = voce.get("latest_version") or voce.get("Latest") or voce.get("latest")
        if not core_id:
            continue
        risultato.append(
            CoreInfo(
                id=core_id,
                installed_version=installed,
                latest_version=latest,
            )
        )
    return risultato


def lista_core_aggiornabili(arduino_cli: Path) -> list[CoreInfo]:
    """Elenca i core installati che hanno una versione più recente disponibile."""
    try:
        output = subprocess.check_output(
            [str(arduino_cli), "core", "list", "--updatable", "--format", "json"],
            text=True,
            timeout=15,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.SubprocessError, OSError:
        return []
    if not output.strip():
        return []
    try:
        dati = json.loads(output)
    except json.JSONDecodeError:
        return []
    # Stessa struttura di lista_core_installati
    if isinstance(dati, list):
        voci = dati
    elif isinstance(dati, dict):
        voci = dati.get("platforms", [])
    else:
        return []
    risultato = []
    for voce in voci:
        if not isinstance(voce, dict):
            continue
        core_id = voce.get("id") or voce.get("ID")
        if core_id:
            risultato.append(
                CoreInfo(
                    id=core_id,
                    installed_version=voce.get("installed_version") or voce.get("Installed"),
                    latest_version=voce.get("latest_version") or voce.get("Latest"),
                )
            )
    return risultato


def costruisci_proxy_url(host: str, porta: int, username: str | None, password: str | None) -> str | None:
    """Costruisce l'URL del proxy con credenziali, gestendo caratteri speciali."""
    if not host:
        return None
    credenziali = ""
    if username:
        credenziali = quote(username, safe="")
        if password:
            credenziali += ":" + quote(password, safe="")
        credenziali += "@"
    return f"http://{credenziali}{host}:{porta}/"


def comando_installazione(
    arduino_cli: Path,
    core_id: str,
    url_extra: str | None = None,
    proxy_url: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Restituisce (argomenti, variabili d'ambiente) per installare un core."""
    args = [str(arduino_cli)]
    if url_extra:
        args += ["--additional-urls", url_extra]
    args += ["core", "install", core_id]

    env = {}
    if proxy_url:
        # arduino-cli legge il proxy da questa variabile d'ambiente
        env["ARDUINO_NETWORK_PROXY"] = proxy_url
    return args, env
