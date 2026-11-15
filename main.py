from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
)


class ArduinoHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # Parole chiave Arduino/C++ (in blu grassetto)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#0000FF"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "\\bsetup\\b",
            "\\bloop\\b",
            "\\bif\\b",
            "\\belse\\b",
            "\\bfor\\b",
            "\\bwhile\\b",
            "\\bint\\b",
            "\\bvoid\\b",
            "\\bboolean\\b",
            "\\bpinMode\\b",
            "\\bdigitalWrite\\b",
            "\\bdigitalRead\\b",
            "\\banalogRead\\b",
            "\\banalogWrite\\b",
            "\\bdelay\\b",
        ]
        for word in keywords:
            self.rules.append((QRegularExpression(word), keyword_format))

        # Commenti (in verde)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#008000"))
        self.rules.append((QRegularExpression("//[^\n]*"), comment_format))

        # Stringhe (in rosso scuro)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#A31515"))
        self.rules.append((QRegularExpression('"[^"]*"'), string_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arduino Didattico")
        self.setMinimumSize(1024, 600)

        # --- Toolbar ---
        toolbar = QToolBar("Principale")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.combo_scheda = QComboBox()
        self.combo_scheda.addItems(["Arduino Uno", "Arduino Nano", "Arduino Nano (Old Bootloader)"])
        self.combo_porta = QComboBox()
        toolbar.addWidget(QLabel(" Scheda: "))
        toolbar.addWidget(self.combo_scheda)
        toolbar.addWidget(QLabel("  Porta: "))
        toolbar.addWidget(self.combo_porta)
        toolbar.addSeparator()

        btn_verifica = QPushButton("✓ Verifica")
        btn_carica = QPushButton("▶ Carica")
        btn_carica.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 6px 14px;")
        btn_monitor = QPushButton("📡 Monitor")
        btn_librerie = QPushButton("📚 Librerie")
        for b in (btn_verifica, btn_carica, btn_monitor, btn_librerie):
            toolbar.addWidget(b)

        # --- Editor ---
        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("font-family: Consolas, monospace; font-size: 16pt;")
        self.highlighter = ArduinoHighlighter(self.editor.document())

        # --- Pannello inferiore ---
        self.tabs = QTabWidget()
        self.console = QPlainTextEdit(readOnly=True)
        self.seriale = QPlainTextEdit(readOnly=True)
        self.tabs.addTab(self.console, "Console")
        self.tabs.addTab(self.seriale, "Monitor Seriale")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.tabs)
        splitter.setSizes([500, 200])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, True)
        self.setCentralWidget(splitter)

        # --- Status bar ---
        sb = QStatusBar()
        self.lbl_pos = QLabel("Riga 1, Col 1")
        self.lbl_stato = QLabel("✅ Pronto")
        sb.addWidget(self.lbl_pos)
        sb.addPermanentWidget(self.lbl_stato)
        self.setStatusBar(sb)

        # Aggiorna posizione cursore
        self.editor.cursorPositionChanged.connect(self._aggiorna_posizione)

    def _aggiorna_posizione(self):
        cur = self.editor.textCursor()
        self.lbl_pos.setText(f"Riga {cur.blockNumber() + 1}, Col {cur.positionInBlock() + 1}")
