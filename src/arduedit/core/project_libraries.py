"""Gestione delle librerie locali al progetto."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class LibreriaProgetto:
    cartella: Path
    nome: str
    versione: str | None = None
    autore: str | None = None

    @property
    def percorso_relativo(self) -> str:
        return f"libraries/{self.cartella.name}"


def cartella_librerie(progetto: Path) -> Path:
    """Restituisce (e crea se serve) la cartella libraries del progetto."""
    lib = Path(progetto) / "libraries"
    lib.mkdir(exist_ok=True)
    return lib


def elenca_librerie(progetto: Path) -> list[LibreriaProgetto]:
    """Elenca le librerie presenti in <progetto>/libraries/."""
    lib_dir = cartella_librerie(progetto)
    risultato: list[LibreriaProgetto] = []

    for sotto in sorted(lib_dir.iterdir()):
        if not sotto.is_dir():
            continue
        if sotto.name.startswith((".", "_")):
            continue

        nome = sotto.name
        versione = None
        autore = None

        props = sotto / "library.properties"
        if props.is_file():
            try:
                for linea in props.read_text(encoding="utf-8", errors="replace").splitlines():
                    linea = linea.strip()
                    if linea.startswith("name="):
                        nome = linea.split("=", 1)[1].strip() or nome
                    elif linea.startswith("version="):
                        versione = linea.split("=", 1)[1].strip()
                    elif linea.startswith("author="):
                        autore = linea.split("=", 1)[1].strip()
            except OSError:
                log.warning("Impossibile leggere library.properties in %s", sotto)

        risultato.append(LibreriaProgetto(cartella=sotto, nome=nome, versione=versione, autore=autore))
    return risultato


def installa_da_zip(progetto: Path, zip_path: Path) -> LibreriaProgetto:
    """Estrae uno ZIP di libreria dentro <progetto>/libraries/.

    Gestisce ZIP con cartella radice singola e ZIP "piatti".
    Solleva ValueError se lo ZIP non è valido o se la libreria esiste già.
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
        raise ValueError("Il file selezionato non è uno ZIP valido.")

    lib_dir = cartella_librerie(progetto)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            nomi = zf.namelist()
            if not nomi:
                raise ValueError("Lo ZIP è vuoto.")

            # Individua la radice comune: se tutti i file sono sotto una
            # singola cartella di primo livello, quella è la radice della libreria.
            primi = {n.split("/")[0] for n in nomi if n.strip("/")}
            if len(primi) == 1 and all("/" in n for n in nomi if n.strip("/")):
                radice = primi.pop()
                membri = [n for n in nomi if n.startswith(radice + "/")]
                destinazione_nome = radice
            else:
                membri = nomi
                destinazione_nome = _nome_da_zip(zip_path)

            destinazione = lib_dir / destinazione_nome
            if destinazione.exists():
                raise ValueError(f"La libreria '{destinazione_nome}' esiste già nel progetto.")

            for membro in membri:
                rel = membro
                if len(primi) == 1 and membro.startswith(radice + "/"):
                    rel = membro[len(radice) + 1 :]
                if not rel or rel.endswith("/"):
                    continue
                if ".." in Path(rel).parts:
                    continue  # sicurezza: niente path traversal
                target = destinazione / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(membro) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

    except zipfile.BadZipFile as exc:
        raise ValueError(f"ZIP corrotto: {exc}") from exc

    # Verifica che sia una libreria Arduino
    contenuto = list(destinazione.rglob("*"))
    if not any(p.suffix in (".h", ".hpp") or p.name == "library.properties" for p in contenuto):
        shutil.rmtree(destinazione, ignore_errors=True)
        raise ValueError("Lo ZIP non sembra una libreria Arduino: mancano file .h o library.properties.")

    librerie = [l for l in elenca_librerie(progetto) if l.cartella.name == destinazione.name]
    return librerie[0] if librerie else LibreriaProgetto(cartella=destinazione, nome=destinazione.name)


def rimuovi_libreria(progetto: Path, nome_cartella: str) -> None:
    """Rimuove una libreria dal progetto."""
    lib_dir = cartella_librerie(progetto)
    target = lib_dir / nome_cartella
    if not target.is_dir():
        raise ValueError(f"Libreria '{nome_cartella}' non trovata.")
    if lib_dir.resolve() not in target.resolve().parents:
        raise ValueError("Percorso non valido.")
    shutil.rmtree(target)


def _nome_da_zip(zip_path: Path) -> str:
    """Deduce un nome di cartella dal nome dello ZIP, rimuovendo la versione."""
    stem = zip_path.stem
    for sep in ("-", "_"):
        if sep in stem:
            parti = stem.split(sep)
            if len(parti) > 1 and parti[-1].replace(".", "").isdigit():
                return sep.join(parti[:-1])
    return stem


def librerie_mancanti_da_errore(testo_errore: str) -> list[str]:
    """Estrae i nomi delle librerie mancanti dagli errori di compilazione.

    Riconosce pattern come:
      fatal error: Servo.h: No such file or directory
      Servo.h: No such file or directory
    """
    import re

    pattern = re.compile(
        r"(?:fatal error:\s*)?([A-Za-z0-9_\-]+)\.h(?:pp)?:\s*No such file or directory",
        re.IGNORECASE,
    )
    nomi = sorted(set(pattern.findall(testo_errore)))
    return nomi


import tempfile
from pathlib import Path


def scarica_libreria_in_progetto(arduino_cli: Path, nome: str, progetto: Path) -> Path:
    """Scarica una libreria dall'indice e la estrae nel progetto."""
    with tempfile.TemporaryDirectory() as tmp:
        # 1) Installazione in una directory temporanea isolata
        env = os.environ.copy()
        env["ARDUINO_DIRECTORIES_USER"] = tmp
        subprocess.run(
            [str(arduino_cli), "lib", "install", nome],
            check=True,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # 2) Individua la cartella della libreria installata
        lib_tmp = Path(tmp) / "libraries" / nome
        if not lib_tmp.is_dir():
            # A volte il nome della cartella differisce; cerca la prima
            candidates = [p for p in (Path(tmp) / "libraries").iterdir() if p.is_dir()]
            if not candidates:
                raise ValueError(f"Libreria '{nome}' non trovata dopo il download.")
            lib_tmp = candidates[0]
        # 3) Copia nella cartella libraries/ del progetto
        dest = cartella_librerie(progetto) / lib_tmp.name
        if dest.exists():
            raise ValueError(f"La libreria '{lib_tmp.name}' esiste già nel progetto.")
        shutil.copytree(lib_tmp, dest)
    return dest
