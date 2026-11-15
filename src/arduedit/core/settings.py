from PySide6.QtCore import QSettings

CHIAVE_ULTIMA_SCHEDA = "ultima_scheda_fqbn"


def _scheda_predefinita() -> str | None:
    return QSettings("Scuola", "ArduEdit").value(CHIAVE_ULTIMA_SCHEDA) or None


def _salva_scheda_predefinita(fqbn: str) -> None:
    QSettings("Scuola", "ArduEdit").setValue(CHIAVE_ULTIMA_SCHEDA, fqbn)
