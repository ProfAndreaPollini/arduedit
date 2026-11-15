"""Enumerazione delle schede supportate dai core installati."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


# Varianti importanti per la scuola che `board listall` non espone
# (sono "menu option" del FQBN, non schede separate).
# Chiave: FQBN base. Valore: lista di (nome visualizzato, FQBN completo).
VARIANTI_SCOLASTICHE: dict[str, list[tuple[str, str]]] = {
    "arduino:avr:nano": [
        ("Arduino Nano (Old Bootloader)", "arduino:avr:nano:cpu=atmega328old"),
    ],
    "arduino:avr:pro": [
        ("Arduino Pro Mini 3.3V/8MHz", "arduino:avr:pro:cpu=8MHzatmega328"),
    ],
}


@dataclass
class BoardInfo:
    fqbn: str
    nome: str
    piattaforma: str

    @property
    def core_id(self) -> str:
        return ":".join(self.fqbn.split(":")[:2])

    @property
    def etichetta(self) -> str:
        if self.piattaforma:
            return f"{self.nome}  ({self.piattaforma})"
        return self.nome


def lista_schede_disponibili(arduino_cli: Path) -> list[BoardInfo]:
    """Elenca le schede supportate dai core installati.

    Restituisce lista vuota (mai eccezioni) in caso di problemi.
    """
    try:
        output = subprocess.check_output(
            [str(arduino_cli), "board", "listall", "--format", "json"],
            text=True,
            timeout=15,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("board listall fallito: %s", exc)
        return []

    if not output.strip():
        return []

    try:
        dati = json.loads(output)
    except json.JSONDecodeError as exc:
        log.warning("JSON di board listall non valido: %s", exc)
        return []

    if isinstance(dati, dict):
        voci = dati.get("boards", [])
    elif isinstance(dati, list):
        voci = dati
    else:
        return []

    risultato: list[BoardInfo] = []
    for v in voci:
        if not isinstance(v, dict):
            continue
        fqbn = v.get("fqbn")
        if not fqbn:
            continue
        nome = v.get("name") or fqbn
        platform = v.get("platform") or {}
        plat_name = ""
        if isinstance(platform, dict):
            meta = platform.get("metadata") or {}
            if isinstance(meta, dict):
                plat_name = meta.get("name") or ""
            plat_name = plat_name or platform.get("id") or ""

        risultato.append(BoardInfo(fqbn=fqbn, nome=nome, piattaforma=plat_name))

        # Aggiungi varianti scolastiche, se pertinenti
        for nome_v, fqbn_v in VARIANTI_SCOLASTICHE.get(fqbn, []):
            risultato.append(BoardInfo(fqbn=fqbn_v, nome=nome_v, piattaforma=plat_name))

    return sorted(risultato, key=lambda b: (b.piattaforma, b.nome))


def _core_fqbn(fqbn: str | None) -> str | None:
    """Primi tre campi del FQBN, ignorando le opzioni dopo ':'."""
    if not fqbn:
        return None
    parti = fqbn.split(":")
    if len(parti) < 3:
        return fqbn
    return ":".join(parti[:3])
