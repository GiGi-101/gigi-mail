import sys
import os
import time
from dotenv import load_dotenv
load_dotenv()

import imaplib
import email

from PyQt6.QtWidgets import QApplication, QMainWindow, QStatusBar, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QTableWidget, QTextBrowser, QDialog, QLineEdit, QTextEdit, QPushButton, QTableWidgetItem
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QThread, QObject, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from smtplib import SMTP_SSL
from email.message import EmailMessage

class MailContentWorker(QObject):
    # send html to MainWindow 
    content_loaded = pyqtSignal(str) 

    def __init__(self, mail_id):
        super().__init__()
        self.mail_id = mail_id

    def run(self):
        try:
            print(f"\n--- Starte Ladevorgang für Mail-ID {self.mail_id} ---")
            
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
                mail_server.select("INBOX")
                
                status, mail_data = mail_server.fetch(self.mail_id, "(RFC822)")

                loaded_msg = email.message_from_bytes(mail_data[0][1])

                content = ""
                if loaded_msg.is_multipart():
                    for part in loaded_msg.walk():
                        if part.get_content_type() == "text/html":
                            content = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    content = loaded_msg.get_payload(decode=True).decode(errors="ignore")
                
                if not content:
                    content = loaded_msg.get_payload(decode=True).decode(errors="ignore")

                self.content_loaded.emit(content)

        except Exception as e:
            self.content_loaded.emit(f"Fehler beim Laden: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GiGi MAils")
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.resize(screen_geo.size())
        
        self.init_ui()
        
    def init_ui(self):
        menuBar = self.menuBar()
        file_menu = menuBar.addMenu("File")
        
        exit_action = QAction("Close the awesome client", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Anwendung schließen")
        
        new_mail_action = QAction("New Mail", self)
        
        exit_action.triggered.connect(self.close)
        new_mail_action.triggered.connect(self.open_compose_dialog)
        file_menu.addAction(exit_action)
        file_menu.addAction(new_mail_action)
        
        # layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        
        #left row
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)
        
        #right row
        content_layout = QVBoxLayout()
        self.overview = QTableWidget()
        self.overview.setColumnCount(2)
        self.overview.setHorizontalHeaderLabels(["Sender", "Subject"])
        self.overview.setRowCount(29)

        #mail content
        self.details = QWebEngineView()
        self.details.setMinimumHeight(400)

        self.overview.cellClicked.connect(self.show_details)
        content_layout.addWidget(self.overview)
        content_layout.addWidget(self.details)
        
        main_layout.addLayout(content_layout)
        
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Bereit")

        self.start_mail_loading()

        self.mail_storage = {}
    
    def open_compose_dialog(self):
        dialog = ComposeDialog()
        dialog.exec()

    def start_mail_loading(self):
        self.loading_thread = QThread()
        self.worker = MailWorker()
        self.worker.moveToThread(self.loading_thread)
        self.loading_thread.started.connect(self.worker.run)
        mail_loaded = self.worker.mail_loaded.connect(self.on_mail_loaded)
        self.loading_thread.start()

    def on_mail_loaded(self, row, sender, subject, mail_id):
        self.overview.setItem(row, 0, QTableWidgetItem(sender))
        self.overview.setItem(row, 1, QTableWidgetItem(subject))
        self.mail_storage[row] = mail_id

    def show_details(self, row, column):
        mail_id = self.mail_storage.get(row)
        if not mail_id:
            return

        self.details.setHtml("<h3>⏳ Lade E-Mail-Inhalt...</h3>")

        # 1. Den Spezial-Worker erstellen und ihm die ID geben
        self.content_worker = MailContentWorker(mail_id)
        self.content_thread = QThread()
        
        self.content_worker.moveToThread(self.content_thread)
        
        # 2. Signale verknüpfen
        self.content_thread.started.connect(self.content_worker.run)
        # Wenn der Text da ist, werfen wir ihn in eine neue Methode "display_content"
        self.content_worker.content_loaded.connect(self.display_content) 
        
        self.content_worker.content_loaded.connect(self.content_thread.quit)
        self.content_worker.content_loaded.connect(self.content_worker.deleteLater)
        self.content_thread.finished.connect(self.content_thread.deleteLater)

        # 3. Worker starten
        self.content_thread.start()

    # Neue, kleine Empfänger-Methode
    def display_content(self, html_content):
        self.details.setHtml(html_content)

class ComposeDialog(QDialog):
    def __init__(self):
        super().__init__()
        dialog_layout = QVBoxLayout()
        self.setLayout(dialog_layout)
        
        self.receiver = QLineEdit()
        self.subject = QLineEdit()
        self.text = QTextEdit()
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_mail)
        dialog_layout.addWidget(self.receiver)
        dialog_layout.addWidget(self.subject)
        dialog_layout.addWidget(self.text)
        dialog_layout.addWidget(self.send_button)
        
    def send_mail(self):
        msg = EmailMessage()
        msg["Subject"] = self.subject.text()
        msg["From"] = os.getenv("EMAIL_USER")
        msg["To"] = self.receiver.text()
        msg.set_content(self.text.toPlainText())
        
        with SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)
        
        self.accept()

class MailWorker(QObject):
    mail_loaded = pyqtSignal(int, str, str, str)
    def run(self):
        with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
            mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
            mail_server.select("INBOX")
            #search all mails
            status, data = mail_server.search(None, "ALL")
            mail_ids = data[0].split()
            mail_ids.reverse()

            for row_index, mail_id in enumerate(mail_ids[:15]):
                status, mail_data = mail_server.fetch(mail_id, "(RFC822.HEADER)")
                loaded_msg = email.message_from_bytes(mail_data[0][1])

                # .get() verhindert Fehler, falls mal ein Betreff komplett leer ist
                loaded_sender = loaded_msg.get("From", "Unbekannt")
                loaded_subject = loaded_msg.get("Subject", "Kein Betreff")

                mail_id_str = mail_id.decode()
                
                self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, mail_id_str)


        
app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()