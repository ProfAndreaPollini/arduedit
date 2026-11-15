# tools/build.py (estratto)
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build_pyinstaller():
    cmd = [
        "uv",
        "run",
        "--group",
        "packaging",
        "pyinstaller",
        "--noconfirm",
        "--windowed",  # niente console (GUI)
        "--name",
        "ArduinoDidattico",
        "--add-data",
        f"{ROOT / 'vendor' / 'arduino-cli.exe'};.",  # Windows
        "--add-data",
        f"{ROOT / 'src' / 'arduino_didattico' / 'resources'};arduino_didattico/resources",
        "--paths",
        str(ROOT / "src"),  # per trovare il pacchetto
        str(ROOT / "src" / "arduino_didattico" / "__main__.py"),
    ]
    subprocess.run(cmd, check=True)
