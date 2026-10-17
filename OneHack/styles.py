# styles.py

MAIN_STYLE = """
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
}

QLineEdit, QTextEdit {
    selection-background-color: #005500;
}

#MenuBackground {
    background-color: transparent; 
}

QPushButton#MenuButton {
    background-color: rgba(20, 20, 20, 220);
    color: #ffffff;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 15px;
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 2px;
}
QPushButton#MenuButton:hover {
    background-color: rgba(40, 40, 40, 255);
    border: 1px solid #00FF00;
    color: #00FF00;
}

QPushButton#BackButton {
    background-color: rgba(20, 20, 20, 200);
    color: #ff4444;
    border: 1px solid #551111;
    border-radius: 5px;
    padding: 8px;
    font-weight: bold;
}
QPushButton#BackButton:hover {
    background-color: rgba(40, 20, 20, 255);
    border: 1px solid #ff0000;
}

QPushButton#ImportButton {
    background-color: #003366;
    color: white;
    border: 1px solid #005599;
    border-radius: 3px;
    padding: 10px;
    font-weight: bold;
}
QPushButton#ImportButton:hover {
    background-color: #004488;
    border: 1px solid #00ffff;
}

QFrame#SidePanel {
    background-color: rgba(15, 15, 15, 240);
    border: 1px solid #222222;
    border-radius: 5px;
}

QLineEdit#LoginInput {
    background-color: #1a1a1a;
    color: #ffffff;
    border: 1px solid #333333;
    border-radius: 3px;
    padding: 8px;
}
QLineEdit#LoginInput:focus {
    border: 1px solid #00FF00;
}

/* Hlavní i vedlejší konzole */
QTextEdit#ConsoleOutput, QTextEdit#SubConsoleOutput {
    background-color: rgba(5, 5, 5, 250);
    color: #00FF00;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 10px;
}

/* Vstup pro hlavní terminál */
QLineEdit#ConsoleInput {
    background-color: #0a0a0a;
    color: #00FF00;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 14px;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 10px;
}
QLineEdit#ConsoleInput:focus {
    border: 1px solid #00AA00;
}

/* Vstup pro Sub-Terminál (aby šlo odpovídat skriptům) */
QLineEdit#SubConsoleInput {
    background-color: #050505;
    color: #00FFFF;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    border: 1px solid #333333;
    border-radius: 3px;
    padding: 8px;
    margin: 5px;
}
QLineEdit#SubConsoleInput:focus {
    border: 1px solid #00FFFF;
}

QFrame#SubTerminalHeader {
    background-color: #1a1a1a;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    border: 1px solid #333333;
    border-bottom: none;
}

QPushButton#CloseSubTerminal {
    background-color: transparent;
    color: #ff4444;
    font-weight: bold;
    font-size: 14px;
    border: none;
}
QPushButton#CloseSubTerminal:hover {
    color: #ff0000;
}
"""