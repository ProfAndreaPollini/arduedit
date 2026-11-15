"""Entry point di ArduEdit.

Eseguibile come `python -m arduedit` oppure tramite il launcher
GUI installato (vedi [project.gui-scripts] in pyproject.toml).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from arduedit import __version__
from arduedit.ui.main_window import MainWindow
from importlib.resources import files
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen


def _installa_excepthook():
    import traceback
    from PySide6.QtWidgets import QMessageBox

    def hook(exc_type, exc, tb):
        testo = "".join(traceback.format_exception(exc_type, exc, tb))
        print(testo, file=sys.stderr)  # se c'è console
        try:
            QMessageBox.critical(
                None,
                "Errore imprevisto",
                f"Si è verificato un errore:\n\n{exc}\n\nDettagli tecnici:\n{testo}",
            )
        except Exception:  # noqa: BLE001
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def main() -> int:
    """Avvia l'applicazione. Restituisce il codice di uscita di Qt."""
    app = QApplication(sys.argv)
    _installa_excepthook()

    # Metadati visibili in "Informazioni su" e in alcuni dialoghi di sistema
    app.setApplicationName("ArduEdit")
    app.setApplicationDisplayName("ArduEdit")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Scuola")

    icona_path = files("arduedit.resources") / "image.ico"
    app.setWindowIcon(QIcon(str(icona_path)))

    # Splash screen: immagine mostrata durante l'inizializzazione
    splash_path = files("arduedit.resources") / "splash.png"
    splash = QSplashScreen(QPixmap(str(splash_path)))
    splash.show()
    app.processEvents()

    # Mostra un messaggio di stato sullo splash
    splash.showMessage(
        "Caricamento schede e toolchain…",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#555555"),
    )
    app.processEvents()

    # La finestra va creata *dopo* QApplication, mai prima
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
