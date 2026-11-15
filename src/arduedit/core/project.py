"""Gestione della struttura di un progetto ArduEdit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TEMPLATE_INO = """void setup() {
  // inizializzazione: eseguita una volta all'avvio
}

void loop() {
  // codice eseguito di continuo
}
"""


@dataclass
class Progetto:
    cartella: Path

    @property
    def nome(self) -> str:
        return self.cartella.name

    @property
    def file_principale(self) -> Path:
        return self.cartella / f"{self.nome}.ino"

    def valido(self) -> bool:
        return self.cartella.is_dir() and self.file_principale.is_file()

    def leggi(self) -> str:
        return self.file_principale.read_text(encoding="utf-8")

    def scrivi(self, testo: str) -> None:
        self.file_principale.write_text(testo, encoding="utf-8")


def crea_progetto(cartella: Path) -> Progetto:
    """Crea una nuova cartella progetto con il file .ino iniziale.

    Solleva ValueError se la cartella esiste già o se il nome non è valido.
    """
    cartella = Path(cartella)
    if cartella.exists():
        raise ValueError(f"La cartella '{cartella}' esiste già.")
    if not cartella.name:
        raise ValueError("Il nome del progetto non può essere vuoto.")
    if any(c in cartella.name for c in r'\/:*?"<>|'):
        raise ValueError("Il nome del progetto contiene caratteri non validi.")
    cartella.mkdir(parents=True)
    progetto = Progetto(cartella=cartella)
    progetto.file_principale.write_text(TEMPLATE_INO, encoding="utf-8")
    return progetto


def apri_progetto(cartella: Path) -> Progetto:
    """Apre una cartella esistente come progetto. Solleva ValueError se non valida."""
    progetto = Progetto(cartella=Path(cartella))
    if not progetto.cartella.is_dir():
        raise ValueError(f"'{cartella}' non è una cartella.")
    if not progetto.file_principale.is_file():
        raise ValueError(
            f"Questa cartella non è un progetto ArduEdit: manca il file '{progetto.file_principale.name}'."
        )
    return progetto
