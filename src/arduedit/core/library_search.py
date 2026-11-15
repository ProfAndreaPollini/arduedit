"""Ricerca di librerie tramite arduino-cli lib search."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class RisultatoRicerca:
    nome: str
    versione: str | None
    autore: str | None
    mantenitore: str | None
    descrizione: str | None  # 'sentence', breve
    categorie: list[str]
    architetture: list[str]
    sito: str | None

    @property
    def etichetta_breve(self) -> str:
        parti = [self.nome]
        if self.versione:
            parti.append(f"v{self.versione}")
        if self.autore:
            parti.append(f"di {self.autore}")
        return "  ".join(parti)


def _estrai_descrizione(v: dict) -> str | None:
    """Cerca 'sentence' in tutti i percorsi noti del JSON di arduino-cli."""
    # 1) a livello top-level (versioni recenti)
    if v.get("sentence"):
        return str(v["sentence"])
    if v.get("paragraph"):
        return str(v["paragraph"])

    # 2) dentro 'latest' (arduino-cli >= 0.33)
    latest = v.get("latest")
    if isinstance(latest, dict):
        if latest.get("sentence"):
            return str(latest["sentence"])
        if latest.get("paragraph"):
            return str(latest["paragraph"])

    # 3) dentro 'releases' (versioni più vecchie)
    releases = v.get("releases")
    if isinstance(releases, dict):
        for rel in releases.values():
            if isinstance(rel, dict):
                if rel.get("sentence"):
                    return str(rel["sentence"])
                if rel.get("paragraph"):
                    return str(rel["paragraph"])
    return None


def cerca_librerie(arduino_cli: Path, query: str, limite: int = 100) -> list[RisultatoRicerca]:
    """Esegue arduino-cli lib search e restituisce i risultati parsati.

    Non solleva eccezioni: in caso di problemi restituisce lista vuota.
    """
    if not query.strip():
        return []

    try:
        output = subprocess.check_output(
            [
                str(arduino_cli),
                "lib",
                "search",
                query,
                "--format",
                "json",
                # "--omit-releases-details",  # CRUCIALE per le prestazioni
            ],
            text=True,
            timeout=30,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("lib search fallito per '%s': %s", query, exc)
        return []

    if not output.strip():
        return []

    try:
        dati = json.loads(output)
    except json.JSONDecodeError as exc:
        log.warning("JSON di lib search non valido: %s", exc)
        return []

    # Il formato può essere una lista piatta o un dict con 'libraries'
    voci: list = []
    if isinstance(dati, list):
        voci = dati
    elif isinstance(dati, dict):
        voci = dati.get("libraries", [])
    else:
        return []

    risultati: list[RisultatoRicerca] = []
    for v in voci[:limite]:
        if not isinstance(v, dict):
            continue
        # I campi possono variare tra versioni; gestiamo i nomi più comuni
        nome = v.get("name") or v.get("Name")
        if not nome:
            continue
        risultati.append(
            RisultatoRicerca(
                nome=nome,
                versione=v.get("version") or v.get("latest", {}).get("version"),
                autore=v.get("author"),
                mantenitore=v.get("maintainer"),
                descrizione=_estrai_descrizione(v),
                # v.get("sentence") or v.get("paragraph"),
                categorie=_lista(v.get("category") or v.get("categories")),
                architetture=_lista(v.get("architectures")),
                sito=v.get("website"),
            )
        )
    return risultati


def _lista(valore) -> list[str]:
    if isinstance(valore, str):
        return [valore]
    if isinstance(valore, list):
        return [str(x) for x in valore]
    return []
