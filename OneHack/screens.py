# screens.py
import sys
import os
import time
import random
import socket
import struct
import subprocess
import shutil
import re
import ssl
from urllib.parse import urlparse

# Zkusíme importovat requests, pokud chybí, apka nespadne, ale řekne si o něj
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication,
                             QPushButton, QLineEdit, QTextEdit, QFormLayout, QFrame, 
                             QGraphicsOpacityEffect, QFileDialog)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QThread, pyqtSignal, QEasingCurve
from PyQt6.QtGui import QFont, QPainter, QColor, QPixmap, QTextCursor, QTextCharFormat
from mcstatus import JavaServer

# ==================== PRACOVNÍ VLÁKNA ====================

class LocalSystemThread(QThread):
    output_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal()
    def __init__(self, command):
        super().__init__()
        self.command = command
    def run(self):
        self.output_signal.emit(f"local@system:~$ {self.command}", "gray")
        try:
            process = subprocess.Popen(
                self.command, shell=True, stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True
            )
            for line in process.stdout:
                self.output_signal.emit(line.strip(), "#00aa00") 
            process.wait()
        except Exception as e:
            self.output_signal.emit(f"[-] SYSTÉMOVÁ CHYBA: {str(e)}", "red")
        self.finished_signal.emit()

class ScriptThread(QThread):
    output_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal()
    
    def __init__(self, script_path):
        super().__init__()
        self.script_path = script_path
        self.process = None
        self.py_cmd = "python3" if sys.platform != "win32" else "python"

    def run(self):
        script_dir = os.path.dirname(os.path.abspath(self.script_path))
        script_file = os.path.basename(self.script_path)
        
        wrapper_code = (
            f"import sys, runpy; "
            f"sys.stdout.isatty = lambda: True; "
            f"sys.stderr.isatty = lambda: True; "
            f"sys.stdin.isatty = lambda: True; "
            f"runpy.run_path('{script_file}', run_name='__main__')"
        )
        
        try:
            self.process = subprocess.Popen(
                [self.py_cmd, "-u", "-c", wrapper_code],
                cwd=script_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1, 
                universal_newlines=True
            )
            
            buffer = ""
            while True:
                char = self.process.stdout.read(1)
                if not char:
                    if buffer: self.output_signal.emit(buffer, "#00FF00")
                    break
                buffer += char
                if char == '\n' or buffer.endswith(": ") or buffer.endswith("> ") or buffer.endswith("? ") or buffer.endswith("] "):
                    self.output_signal.emit(buffer, "#00FF00")
                    buffer = ""
            
            self.process.wait()
            if self.process.returncode == 0:
                self.output_signal.emit("[*] Skript úspěšně dokončen (Exit 0).\n", "gray")
            else:
                self.output_signal.emit(f"[-] Skript spadl s chybovým kódem: {self.process.returncode}\n", "red")
        except Exception as e:
            self.output_signal.emit(f"[-] KRITICKÁ CHYBA SPOUŠTĚČE: {str(e)}\n", "red")
        self.finished_signal.emit()

    def send_input(self, text):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
            except: pass

    def kill_process(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.output_signal.emit("[!] PROCES BYL NÁSILNĚ UKONČEN.\n", "red")

# === NOVÉ: Vlákno pro skenování WEBU ===
class WebScannerThread(QThread):
    log_signal = pyqtSignal(str, str)
    telemetry_signal = pyqtSignal(str, str, str, str) # IP, Ping, Status, Server

    def __init__(self, url):
        super().__init__()
        if not url.startswith("http"):
            url = "https://" + url
        self.url = url

    def run(self):
        if not HAS_REQUESTS:
            self.log_signal.emit("[-] CHYBA: Chybí modul 'requests'!", "red")
            self.log_signal.emit("Tip: Zadej do terminálu '!pip3 install requests' pro jeho instalaci.\n", "yellow")
            self.telemetry_signal.emit("N/A", "N/A", "CHYBA", "N/A")
            return

        try:
            parsed = urlparse(self.url)
            domain = parsed.netloc or parsed.path
            
            self.log_signal.emit(f"[*] Zahajuji OSINT analýzu cíle: {domain}...\n", "yellow")
            
            # 1. IP a DNS
            self.log_signal.emit("[*] Překládám DNS záznamy...", "gray")
            try:
                ip = socket.gethostbyname(domain)
                self.log_signal.emit(f"[+] IP Adresa: {ip}\n", "#00FFFF")
            except:
                ip = "Neznámá"
                self.log_signal.emit("[-] Nelze přeložit DNS.\n", "red")

            # 2. HTTP Request (Odezva a Hlavičky)
            self.log_signal.emit("[*] Odesílám HTTP GET request...", "gray")
            start_time = time.time()
            response = requests.get(self.url, timeout=5)
            ping_ms = int((time.time() - start_time) * 1000)
            
            status = str(response.status_code)
            server_type = response.headers.get("Server", "Skrytý")
            
            status_color = "#00FF00" if response.ok else "orange"
            self.log_signal.emit(f"[+] Status Kód: {status}", status_color)
            self.log_signal.emit(f"[+] Odezva serveru: {ping_ms} ms", "#00FF00")
            self.log_signal.emit(f"[+] Technologie serveru: {server_type}\n", "cyan")
            
            self.log_signal.emit("[*] Nalezené bezpečnostní hlavičky:", "gray")
            found_headers = False
            for key, val in response.headers.items():
                if key.lower() in ['x-powered-by', 'x-frame-options', 'content-security-policy', 'strict-transport-security', 'server']:
                    self.log_signal.emit(f"    - {key}: {val}", "white")
                    found_headers = True
            if not found_headers:
                self.log_signal.emit("    (Žádné zajímavé hlavičky nenalezeny)", "gray")
            self.log_signal.emit("\n", "")

            # 3. SSL Certifikát
            if self.url.startswith("https"):
                self.log_signal.emit("[*] Extrahuji SSL/TLS certifikát...", "gray")
                try:
                    ctx = ssl.create_default_context()
                    with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
                        s.connect((domain, 443))
                        cert = s.getpeercert()
                        issuer = dict(x[0] for x in cert['issuer'])
                        self.log_signal.emit(f"[+] Vydavatel SSL: {issuer.get('organizationName', issuer.get('commonName', 'Neznámý'))}", "#00FFFF")
                        self.log_signal.emit(f"[+] Platnost do: {cert['notAfter']}\n", "#00FFFF")
                except Exception as e:
                    self.log_signal.emit(f"[-] SSL Chyba: {str(e)}\n", "red")

            self.log_signal.emit("[+] Analýza úspěšně dokončena.\n", "#00FF00")
            self.telemetry_signal.emit(ip, f"{ping_ms} ms", status, server_type)

        except requests.exceptions.RequestException as e:
            self.log_signal.emit(f"[-] CHYBA SPOJENÍ: {str(e)}\n", "red")
            self.telemetry_signal.emit("N/A", "N/A", "TIMEOUT", "N/A")
        except Exception as e:
            self.log_signal.emit(f"[-] FATÁLNÍ CHYBA SKENERU: {str(e)}\n", "red")
            self.telemetry_signal.emit("N/A", "N/A", "ERROR", "N/A")


class RawRcon:
    def __init__(self, host, port, password):
        self.host = host; self.port = port; self.password = password
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
    def connect(self):
        self.sock.connect((self.host, self.port))
        self._send(3, self.password)
        typ, req_id, _ = self._read()
        if req_id == -1: raise Exception("Neplatné RCON heslo!")
    def command(self, cmd):
        self._send(2, cmd)
        _, _, payload = self._read()
        return payload
    def _send(self, typ, msg):
        body = struct.pack('<ii', 0, typ) + msg.encode('utf-8') + b'\x00\x00'
        self.sock.send(struct.pack('<i', len(body)) + body)
    def _read(self):
        data = self.sock.recv(4)
        if not data: raise Exception("Spojení ztraceno")
        length = struct.unpack('<i', data)[0]
        packet = self.sock.recv(length)
        req_id, typ = struct.unpack('<ii', packet[:8])
        payload = packet[8:-2].decode('utf-8', errors='ignore')
        return typ, req_id, payload
    def disconnect(self):
        self.sock.close()

class ConnectionThread(QThread):
    log_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(object, str)
    def __init__(self, ip, game_port, rcon_port, password):
        super().__init__()
        self.ip = ip; self.game_port = game_port; self.rcon_port = rcon_port; self.password = password
    def run(self):
        self.log_signal.emit(f"[*] Skenování hostitele {self.ip}:{self.game_port}...\n", "yellow")
        try:
            server = JavaServer.lookup(f"{self.ip}:{self.game_port}")
            server.status() 
            self.log_signal.emit("[+] Server nalezen.\n", "#00FFFF")
        except:
            self.log_signal.emit("[-] Server neodpovídá na Game Portu.\n", "orange")
        if not self.password:
            self.log_signal.emit("[*] Režim HOSTA (Guest) aktivován.\n", "cyan")
            self.finished_signal.emit(None, "GUEST")
            return
        self.log_signal.emit(f"[*] Navazuji RCON...\n", "yellow")
        try:
            rcon = RawRcon(self.ip, self.rcon_port, self.password)
            rcon.connect()
            self.log_signal.emit("[+] AUTHENTICATION SUCCESSFUL.\n", "#00FF00")
            self.finished_signal.emit(rcon, "ADMIN")
        except Exception as e:
            self.log_signal.emit(f"[-] FÁTÁLNÍ CHYBA RCON: {str(e)}\n", "red")
            self.finished_signal.emit(None, "RCON_ERROR")

class TelemetryThread(QThread):
    update_signal = pyqtSignal(str, str)
    def __init__(self, ip, game_port):
        super().__init__()
        self.ip = ip; self.game_port = game_port; self.running = True
    def run(self):
        while self.running:
            try:
                server = JavaServer.lookup(f"{self.ip}:{self.game_port}")
                status = server.status()
                self.update_signal.emit(f"{status.players.online}/{status.players.max}", f"{round(status.latency)} ms")
            except:
                self.update_signal.emit("Odpojeno", "N/A")
            for _ in range(50):
                if not self.running: break
                time.sleep(0.1)
    def stop(self): self.running = False


# ==================== UI WIDGETY A OBRAZOVKY ====================

class SubTerminalWidget(QFrame):
    def __init__(self, script_path, title_name):
        super().__init__()
        self.script_path = script_path
        self.script_name = title_name
        self.setObjectName("SidePanel")
        
        self.is_running = False
        self.thread = None
        self.is_closing = False
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        self.setMaximumWidth(0)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setObjectName("SubTerminalHeader")
        header_layout = QHBoxLayout()
        title = QLabel(f"⚙ {title_name}")
        title.setStyleSheet("color: cyan; font-weight: bold; font-family: Consolas;")
        self.btn_close = QPushButton("✖")
        self.btn_close.setObjectName("CloseSubTerminal")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.close_terminal)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close)
        header.setLayout(header_layout)
        
        self.console_output = QTextEdit()
        self.console_output.setObjectName("SubConsoleOutput")
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("border-top: none; border-top-left-radius: 0px; border-top-right-radius: 0px;")
        
        self.input_field = QLineEdit()
        self.input_field.setObjectName("SubConsoleInput")
        self.input_field.returnPressed.connect(self.handle_input)
        
        layout.addWidget(header)
        layout.addWidget(self.console_output)
        layout.addWidget(self.input_field)
        self.setLayout(layout)
        
        self.log("[*] Vytvářím oddělený sandbox...\n", "gray")
        
        self.anim = QPropertyAnimation(self, b"maximumWidth")
        self.anim.setDuration(450)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(0)
        self.anim.setEndValue(450)
        self.anim.finished.connect(self.on_opened)
        self.anim.start()

    def on_opened(self):
        if self.is_closing: return
        self.log("[+] Sandbox připraven.\n", "#00FFFF")
        self.input_field.setText(f"run {self.script_name}")
        self.input_field.setFocus()

    def handle_input(self):
        text = self.input_field.text().strip()
        if not text: return
        self.input_field.clear()

        if self.is_running and self.thread:
            self.log(f"{text}\n", "cyan") 
            self.thread.send_input(text) 
        else:
            self.log(f"> {text}\n", "white")
            if text.lower().startswith("run"): self.start_script()

    def start_script(self):
        self.is_running = True
        self.log("[*] Bootuji modul...\n", "yellow")
        self.thread = ScriptThread(self.script_path)
        self.thread.output_signal.connect(self.log)
        self.thread.finished_signal.connect(self.on_script_finished)
        self.thread.start()

    def on_script_finished(self):
        self.is_running = False
        if not self.is_closing:
            self.input_field.setEnabled(True)
            self.input_field.setText(f"run {self.script_name}")
            self.input_field.setFocus()

    def log(self, message, color="#00FF00"):
        clean_message = self.ansi_escape.sub('', str(message))
        cursor = self.console_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        cursor.insertText(clean_message)
        self.console_output.verticalScrollBar().setValue(self.console_output.verticalScrollBar().maximum())

    def close_terminal(self):
        self.is_closing = True
        if self.is_running and self.thread: self.thread.kill_process()
        self.anim.setStartValue(self.width())
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()

# === NOVÉ OKNO PRO WEB DASHBOARD ===
class WebTerminal(QWidget):
    def __init__(self, go_back_callback):
        super().__init__()
        self.go_back_callback = go_back_callback
        self.setStyleSheet("background-color: #0a0a0a;")
        
        main_layout = QHBoxLayout()
        
        # --- LEVÝ PANEL (Vstupy) ---
        left_panel = QFrame()
        left_panel.setObjectName("SidePanel")
        left_panel.setFixedWidth(260)
        left_layout = QFormLayout()
        
        header = QLabel("WEB OSINT SKENER")
        header.setStyleSheet("color: #00FFFF; font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        
        self.url_input = QLineEdit()
        self.url_input.setObjectName("LoginInput")
        self.url_input.setPlaceholderText("např. https://seznam.cz")
        
        self.btn_scan = QPushButton("ZAHÁJIT SKEN")
        self.btn_scan.setStyleSheet("background-color: #005577; color: white; padding: 10px; border-radius: 3px; font-weight: bold;")
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.clicked.connect(self.start_scan)
        
        self.btn_import = QPushButton("⬇ IMPORT SKRIPTU")
        self.btn_import.setObjectName("ImportButton")
        self.btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import.clicked.connect(self.import_script)
        
        self.btn_back = QPushButton("← ZPĚT DO MENU")
        self.btn_back.setObjectName("BackButton")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.disconnect_and_go_back)
        
        left_layout.addRow(header)
        left_layout.addRow("Cílová URL:", self.url_input)
        left_layout.addRow("", self.btn_scan)
        left_layout.addRow("", self.btn_import)
        left_layout.addRow("", QLabel("")) 
        left_layout.addRow("", self.btn_back)
        left_panel.setLayout(left_layout)
        
        # --- STŘEDNÍ KONTEJNER (Pro Terminály) ---
        self.terminals_container_layout = QHBoxLayout()
        main_terminal_container = QWidget()
        center_layout = QVBoxLayout(main_terminal_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        self.console_output = QTextEdit()
        self.console_output.setObjectName("ConsoleOutput")
        self.console_output.setReadOnly(True)
        
        input_layout = QHBoxLayout()
        prefix = QLabel("osint@onehask:~$")
        prefix.setStyleSheet("color: #00FFFF; font-family: Consolas; font-size: 14px; font-weight: bold;")
        
        self.console_input = QLineEdit()
        self.console_input.setObjectName("ConsoleInput")
        self.console_input.setPlaceholderText("Napiš ! pro PC | start [jmeno] pro modul")
        self.console_input.returnPressed.connect(self.send_command)
        
        input_layout.addWidget(prefix)
        input_layout.addWidget(self.console_input)
        
        center_layout.addWidget(self.console_output)
        center_layout.addLayout(input_layout)
        self.terminals_container_layout.addWidget(main_terminal_container)
        
        # --- PRAVÝ PANEL (Live Web Info) ---
        right_panel = QFrame()
        right_panel.setObjectName("SidePanel")
        right_panel.setFixedWidth(220)
        right_layout = QVBoxLayout()
        
        info_header = QLabel("WEB TELEMETRY")
        info_header.setStyleSheet("color: #00FFFF; font-weight: bold; font-size: 16px;")
        self.info_ip = QLabel("IP Adresa: --")
        self.info_ip.setStyleSheet("color: white;")
        self.info_ping = QLabel("Odezva: -- ms")
        self.info_ping.setStyleSheet("color: white;")
        self.info_status = QLabel("Status Kód: --")
        self.info_status.setStyleSheet("color: white;")
        self.info_server = QLabel("Server: --")
        self.info_server.setStyleSheet("color: gray;")
        
        right_layout.addWidget(info_header)
        right_layout.addWidget(self.info_ip)
        right_layout.addWidget(self.info_ping)
        right_layout.addWidget(self.info_status)
        right_layout.addWidget(self.info_server)
        right_layout.addStretch()
        right_panel.setLayout(right_layout)
        
        main_layout.addWidget(left_panel)
        main_layout.addLayout(self.terminals_container_layout)
        main_layout.addWidget(right_panel)
        self.setLayout(main_layout)
        
        self.log("OneHask OSINT Modul Ready.\n", "#888888")
        self.log("Zadej URL adresu vlevo a klikni na 'ZAHÁJIT SKEN'.\n", "cyan")

    def log(self, message, color="#00FFFF"):
        msg_safe = str(message).replace("<", "&lt;").replace(">", "&gt;")
        self.console_output.append(f"<span style='color:{color}'>{msg_safe}</span>")
        self.console_output.verticalScrollBar().setValue(self.console_output.verticalScrollBar().maximum())

    def import_script(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Vyber Python modul", "", "Python Files (*.py)")
        if file_path:
            os.makedirs("scripts", exist_ok=True)
            filename = os.path.basename(file_path)
            dest_path = os.path.join("scripts", filename)
            try:
                shutil.copy(file_path, dest_path)
                self.log(f"[+] Modul nahrán! Napiš 'start {filename}'.\n", "#00FFFF")
                QApplication.beep()
            except Exception as e:
                self.log(f"[-] CHYBA: {str(e)}\n", "red")

    def start_scan(self):
        url = self.url_input.text().strip()
        if not url:
            self.log("[-] CHYBA: Musíš zadat URL adresu cíle!\n", "red")
            return
            
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("SKENOVÁNÍ...")
        
        # Reset hodnot napravo
        self.info_ip.setText("IP Adresa: Hledám...")
        self.info_ping.setText("Odezva: Hledám...")
        
        self.scanner_thread = WebScannerThread(url)
        self.scanner_thread.log_signal.connect(self.log)
        self.scanner_thread.telemetry_signal.connect(self.update_telemetry)
        self.scanner_thread.finished.connect(lambda: self.btn_scan.setEnabled(True))
        self.scanner_thread.finished.connect(lambda: self.btn_scan.setText("ZAHÁJIT SKEN"))
        self.scanner_thread.start()

    def update_telemetry(self, ip, ping, status, server):
        self.info_ip.setText(f"IP Adresa: {ip}")
        self.info_ping.setText(f"Odezva: {ping}")
        self.info_status.setText(f"Status Kód: {status}")
        self.info_server.setText(f"Server: {server}")
        
        if "ERROR" in status or "TIMEOUT" in status:
            self.info_status.setStyleSheet("color: red; font-weight: bold;")
        elif status.startswith("2") or status.startswith("3"):
            self.info_status.setStyleSheet("color: #00FF00; font-weight: bold;")

    def send_command(self):
        cmd = self.console_input.text().strip()
        if not cmd: return
        self.console_input.clear()

        if cmd.lower().startswith("start "):
            script_name = cmd.split(" ", 1)[1].strip()
            if not script_name.endswith(".py"): script_name += ".py" 
            script_path = os.path.join("scripts", script_name)
            
            if os.path.exists(script_path):
                self.log(f"[*] Bootuji sub-terminál pro: {script_name}...\n", "yellow")
                new_terminal = SubTerminalWidget(script_path, script_name)
                self.terminals_container_layout.addWidget(new_terminal)
            else:
                self.log(f"[-] CHYBA: Skript '{script_name}' nenalezen.\n", "red")
            return

        if cmd.startswith("!"):
            sys_cmd = cmd[1:].strip() 
            if sys_cmd.startswith("ping") and "-c" not in sys_cmd and sys.platform != "win32":
                sys_cmd = sys_cmd.replace("ping", "ping -c 4")
            self.console_input.setEnabled(False)
            self.sys_thread = LocalSystemThread(sys_cmd)
            self.sys_thread.output_signal.connect(self.log)
            self.sys_thread.finished_signal.connect(lambda: self.console_input.setEnabled(True))
            self.sys_thread.finished_signal.connect(lambda: self.console_input.setFocus())
            self.sys_thread.start()
            return

        self.log(f"osint@onehask:~$ {cmd}\n", "white")
        self.log("[-] Neznámý příkaz. Zadej URL vlevo, nebo použij '!' pro lokální PC.\n", "red")

    def disconnect_and_go_back(self):
        QApplication.beep()
        self.go_back_callback()


class HackerLoadingScreen(QWidget):
    def __init__(self, switch_callback):
        super().__init__()
        self.switch_callback = switch_callback
        self.setStyleSheet("background-color: black;")
        layout = QVBoxLayout()
        self.label = QLabel("")
        self.label.setFont(QFont("Consolas", 12))
        self.label.setStyleSheet("color: #00FF00;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.messages = [
            "[OK] Booting OneHask Kernel v1.0.0-DEV...",
            "[OK] Mounting virtual drives...",
            "[*] Initializing OSINT Framework...",
            "[*] Loading Telemetry & System modules...",
            "[SYSTEM] Access Granted."
        ]
        self.current_msg = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_text)
        self.timer.start(400)
    def update_text(self):
        if self.current_msg < len(self.messages):
            self.label.setText(self.label.text() + "\n" + self.messages[self.current_msg])
            self.current_msg += 1
        else:
            self.timer.stop()
            QTimer.singleShot(800, self.switch_callback)

class MainMenu(QWidget):
    def __init__(self, switch_to_mc, switch_to_web):
        super().__init__()
        self.switch_to_mc = switch_to_mc
        self.switch_to_web = switch_to_web
        self.setObjectName("MenuBackground")
        self.matrix_font_size = 14
        self.columns = 0
        self.drops = []
        self.chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%^&*"
        self.buffer = None
        self.matrix_timer = QTimer(self)
        self.matrix_timer.timeout.connect(self.draw_matrix)
        self.matrix_timer.start(50)
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(1500)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("ONEHASK")
        title.setFont(QFont("Arial", 60, QFont.Weight.Bold))
        title.setStyleSheet("color: white; letter-spacing: 5px; background-color: rgba(0,0,0,150); border-radius: 10px; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("VERSION 1.0.0-DEV")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setStyleSheet("color: #00FF00; letter-spacing: 3px; background-color: rgba(0,0,0,150); padding: 5px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_web = QPushButton("WEB OSINT DASHBOARD")
        self.btn_web.setObjectName("MenuButton")
        self.btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_web.clicked.connect(self.on_web_click)
        self.btn_mc = QPushButton("MINECRAFT TERMINAL")
        self.btn_mc.setObjectName("MenuButton")
        self.btn_mc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mc.clicked.connect(self.on_mc_click)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(60)
        layout.addWidget(self.btn_web)
        layout.addSpacing(15)
        layout.addWidget(self.btn_mc)
        self.setLayout(layout)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.buffer = QPixmap(self.size())
        self.buffer.fill(Qt.GlobalColor.black)
        self.columns = self.width() // self.matrix_font_size + 1
        self.drops = [random.randint(-50, 0) for _ in range(self.columns)]
    def draw_matrix(self):
        if self.buffer is None: return
        painter = QPainter(self.buffer)
        painter.fillRect(self.buffer.rect(), QColor(0, 0, 0, 40))
        painter.setFont(QFont("Consolas", self.matrix_font_size, QFont.Weight.Bold))
        for i in range(len(self.drops)):
            char = random.choice(self.chars)
            x = i * self.matrix_font_size
            y = self.drops[i] * self.matrix_font_size
            painter.setPen(QColor(0, 255, 0))
            painter.drawText(x, y, char)
            if y > self.height() and random.random() > 0.95: self.drops[i] = 0
            self.drops[i] += 1
        painter.end()
        self.update()
    def paintEvent(self, event):
        painter = QPainter(self)
        if self.buffer: painter.drawPixmap(0, 0, self.buffer)
    def showEvent(self, event):
        self.anim.start()
        super().showEvent(event)
    def on_mc_click(self):
        QApplication.beep()
        self.switch_to_mc()
    def on_web_click(self):
        QApplication.beep()
        self.switch_to_web()

class MinecraftTerminal(QWidget):
    def __init__(self, go_back_callback):
        super().__init__()
        self.mcr = None
        self.telemetry = None 
        self.go_back_callback = go_back_callback
        self.setStyleSheet("background-color: #0a0a0a;")
        main_layout = QHBoxLayout()
        left_panel = QFrame()
        left_panel.setObjectName("SidePanel")
        left_panel.setFixedWidth(260)
        left_layout = QFormLayout()
        header = QLabel("SERVER UPLINK")
        header.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        self.ip_input = QLineEdit()
        self.ip_input.setObjectName("LoginInput")
        self.ip_input.setPlaceholderText("IP (např. 185.83.152.84)")
        self.game_port_input = QLineEdit("25565")
        self.game_port_input.setObjectName("LoginInput")
        self.rcon_port_input = QLineEdit("25575")
        self.rcon_port_input.setObjectName("LoginInput")
        self.pass_input = QLineEdit()
        self.pass_input.setObjectName("LoginInput")
        self.pass_input.setPlaceholderText("Prázdné = GUEST")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.btn_connect = QPushButton("PŘIPOJIT K SÍTI")
        self.btn_connect.setStyleSheet("background-color: #005500; color: white; padding: 10px; border-radius: 3px; font-weight: bold;")
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.clicked.connect(self.start_connection)
        self.btn_import = QPushButton("⬇ IMPORT SKRIPTU")
        self.btn_import.setObjectName("ImportButton")
        self.btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import.clicked.connect(self.import_script)
        self.btn_back = QPushButton("← ZPĚT DO MENU")
        self.btn_back.setObjectName("BackButton")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.disconnect_and_go_back)
        left_layout.addRow(header)
        left_layout.addRow("IP Adresa:", self.ip_input)
        left_layout.addRow("Hrací Port:", self.game_port_input)
        left_layout.addRow("RCON Port:", self.rcon_port_input)
        left_layout.addRow("Heslo:", self.pass_input)
        left_layout.addRow("", self.btn_connect)
        left_layout.addRow("", self.btn_import)
        left_layout.addRow("", QLabel("")) 
        left_layout.addRow("", self.btn_back)
        left_panel.setLayout(left_layout)
        
        self.terminals_container_layout = QHBoxLayout()
        main_terminal_container = QWidget()
        center_layout = QVBoxLayout(main_terminal_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.console_output = QTextEdit()
        self.console_output.setObjectName("ConsoleOutput")
        self.console_output.setReadOnly(True)
        input_layout = QHBoxLayout()
        prefix = QLabel("root@onehask:~$")
        prefix.setStyleSheet("color: #00FF00; font-family: Consolas; font-size: 14px; font-weight: bold;")
        self.console_input = QLineEdit()
        self.console_input.setObjectName("ConsoleInput")
        self.console_input.setPlaceholderText("Napiš ! pro PC | start [jmeno] pro modul")
        self.console_input.returnPressed.connect(self.send_command)
        input_layout.addWidget(prefix)
        input_layout.addWidget(self.console_input)
        center_layout.addWidget(self.console_output)
        center_layout.addLayout(input_layout)
        self.terminals_container_layout.addWidget(main_terminal_container)
        
        right_panel = QFrame()
        right_panel.setObjectName("SidePanel")
        right_panel.setFixedWidth(220)
        right_layout = QVBoxLayout()
        info_header = QLabel("LIVE TELEMETRY")
        info_header.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 16px;")
        self.info_mode = QLabel("Režim: NEZNÁMÝ")
        self.info_mode.setStyleSheet("color: gray;")
        self.info_ping = QLabel("Ping: -- ms")
        self.info_ping.setStyleSheet("color: white;")
        self.info_players = QLabel("Hráči: --")
        self.info_players.setStyleSheet("color: white;")
        right_layout.addWidget(info_header)
        right_layout.addWidget(self.info_mode)
        right_layout.addWidget(self.info_ping)
        right_layout.addWidget(self.info_players)
        right_layout.addStretch()
        right_panel.setLayout(right_layout)
        
        main_layout.addWidget(left_panel)
        main_layout.addLayout(self.terminals_container_layout)
        main_layout.addWidget(right_panel)
        self.setLayout(main_layout)
        
        self.log("OneHask OS v1.0.0-DEV Terminal Ready.\n", "#888888")

    def log(self, message, color="#00FF00"):
        msg_safe = str(message).replace("<", "&lt;").replace(">", "&gt;")
        self.console_output.append(f"<span style='color:{color}'>{msg_safe}</span>")
        self.console_output.verticalScrollBar().setValue(self.console_output.verticalScrollBar().maximum())

    def import_script(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Vyber Python modul k importu", "", "Python Files (*.py)")
        if file_path:
            os.makedirs("scripts", exist_ok=True)
            filename = os.path.basename(file_path)
            dest_path = os.path.join("scripts", filename)
            try:
                shutil.copy(file_path, dest_path)
                self.log(f"[+] Modul nahrán! Napiš 'start {filename}' pro spuštění vedle sebe.\n", "#00FFFF")
                QApplication.beep()
            except Exception as e:
                self.log(f"[-] CHYBA při importu: {str(e)}\n", "red")

    def start_connection(self):
        ip = self.ip_input.text().strip()
        g_port = self.game_port_input.text().strip()
        r_port = self.rcon_port_input.text().strip()
        password = self.pass_input.text()
        if not ip or not g_port or not r_port:
            self.log("[-] CHYBA: Musíš zadat IP a oba porty!\n", "red")
            return
        try:
            game_port = int(g_port); rcon_port = int(r_port)
        except:
            self.log("[-] CHYBA: Port musí být číslo!\n", "red")
            return
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("PŘIPOJUJI...")
        self.conn_thread = ConnectionThread(ip, game_port, rcon_port, password)
        self.conn_thread.log_signal.connect(self.log)
        self.conn_thread.finished_signal.connect(self.on_connection_finished)
        self.conn_thread.start()

    def on_connection_finished(self, rcon_obj, mode):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("PŘIPOJIT K SÍTI")
        if mode == "ADMIN":
            self.mcr = rcon_obj
            self.info_mode.setText("Režim: ADMIN (RCON)")
            self.info_mode.setStyleSheet("color: #00FF00; font-weight: bold;")
        elif mode == "GUEST":
            self.mcr = None
            self.info_mode.setText("Režim: GUEST (Ping)")
            self.info_mode.setStyleSheet("color: cyan;")
        else:
            self.mcr = None
            self.info_mode.setText("Režim: OFFLINE")
            self.info_mode.setStyleSheet("color: red;")
            return
        self.telemetry = TelemetryThread(self.ip_input.text().strip(), int(self.game_port_input.text()))
        self.telemetry.update_signal.connect(self.update_telemetry_ui)
        self.telemetry.start()

    def update_telemetry_ui(self, players, ping):
        self.info_players.setText(f"Hráči: {players}")
        self.info_ping.setText(f"Ping: {ping}")
        if ping == "N/A": self.info_ping.setStyleSheet("color: red;")
        else: self.info_ping.setStyleSheet("color: white;")

    def send_command(self):
        cmd = self.console_input.text().strip()
        if not cmd: return
        self.console_input.clear()
        if cmd.lower().startswith("start "):
            script_name = cmd.split(" ", 1)[1].strip()
            if not script_name.endswith(".py"): script_name += ".py" 
            script_path = os.path.join("scripts", script_name)
            if os.path.exists(script_path):
                self.log(f"[*] Bootuji sub-terminál pro: {script_name}...\n", "yellow")
                new_terminal = SubTerminalWidget(script_path, script_name)
                self.terminals_container_layout.addWidget(new_terminal)
            else:
                self.log(f"[-] CHYBA: Skript '{script_name}' nenalezen.\n", "red")
            return
        if cmd.startswith("!"):
            sys_cmd = cmd[1:].strip() 
            if sys_cmd.startswith("ping") and "-c" not in sys_cmd and sys.platform != "win32":
                sys_cmd = sys_cmd.replace("ping", "ping -c 4")
            self.console_input.setEnabled(False)
            self.sys_thread = LocalSystemThread(sys_cmd)
            self.sys_thread.output_signal.connect(self.log)
            self.sys_thread.finished_signal.connect(lambda: self.console_input.setEnabled(True))
            self.sys_thread.finished_signal.connect(lambda: self.console_input.setFocus())
            self.sys_thread.start()
            return
        self.log(f"root@onehask:~$ {cmd}\n", "white")
        if not self.mcr:
            self.log("[-] ZAMÍTNUTO: Nemáš RCON práva.\n", "red")
            return
        try:
            response = self.mcr.command(cmd)
            if response: self.log(f"{response}\n", "#00FFFF")
        except Exception as e:
            self.log(f"[-] ZTRÁTA SPOJENÍ: {str(e)}\n", "red")
            self.info_mode.setText("Režim: OFFLINE")
            self.info_mode.setStyleSheet("color: red;")
            self.mcr = None

    def disconnect_and_go_back(self):
        if self.mcr:
            try: self.mcr.disconnect()
            except: pass
            self.mcr = None
        if self.telemetry:
            self.telemetry.stop()
            self.telemetry.wait() 
            self.telemetry = None
        self.info_mode.setText("Režim: NEZNÁMÝ")
        self.info_mode.setStyleSheet("color: gray;")
        self.info_players.setText("Hráči: --")
        self.info_ping.setText("Ping: -- ms")
        self.log("Odpojeno. Návrat do menu...\n", "yellow")
        QApplication.beep()
        self.go_back_callback()