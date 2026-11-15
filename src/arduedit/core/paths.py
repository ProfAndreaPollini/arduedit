import os
import shutil
import sys
from pathlib import Path


def trova_arduino_cli() -> Path | None:
    """Trova arduino-cli.exe, con priorità alla cartella di sistema condivisa."""
    nomi = ("arduino-cli.exe", "arduino-cli")  # Windows + altri OS

    # 1. ARDUINO_DIRECTORIES_DATA (installazione centralizzata di laboratorio)
    data_dir = os.environ.get("ARDUINO_DIRECTORIES_DATA")
    if data_dir:
        for nome in nomi:
            candidate = Path(data_dir) / nome
            if candidate.exists():
                return candidate

    # 2. accanto all'eseguibile (bundle PyInstaller/Nuitka)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for nome in nomi:
            candidate = exe_dir / nome
            if candidate.exists():
                return candidate

    # 3. vendor del progetto (sviluppo)
    project_root = Path(__file__).resolve().parents[3]
    for nome in nomi:
        candidate = project_root / "vendor" / nome
        if candidate.exists():
            return candidate

    # 4. PATH di sistema
    found = shutil.which("arduino-cli")
    return Path(found) if found else None
