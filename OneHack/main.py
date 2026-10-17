# main.py
import sys
from PyQt6.QtWidgets import QApplication, QStackedWidget
from screens import HackerLoadingScreen, MainMenu, MinecraftTerminal, WebTerminal
from styles import MAIN_STYLE

class OneHaskCore(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OneHask | Server & Web Administration")
        self.resize(1200, 700) # Zvětšeno pro lepší přehlednost
        
        # Předáváme funkce pro přepínání oken
        self.loading_screen = HackerLoadingScreen(self.show_menu)
        self.main_menu = MainMenu(self.show_minecraft, self.show_web)
        self.mc_terminal = MinecraftTerminal(self.show_menu)
        self.web_terminal = WebTerminal(self.show_menu)
        
        self.addWidget(self.loading_screen)
        self.addWidget(self.main_menu)
        self.addWidget(self.mc_terminal)
        self.addWidget(self.web_terminal)
        
        self.setCurrentWidget(self.loading_screen)

    def show_menu(self):
        self.setCurrentWidget(self.main_menu)

    def show_minecraft(self):
        self.setCurrentWidget(self.mc_terminal)
        
    def show_web(self):
        self.setCurrentWidget(self.web_terminal)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(MAIN_STYLE)
    
    core = OneHaskCore()
    core.show()
    
    sys.exit(app.exec())