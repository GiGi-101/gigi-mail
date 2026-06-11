import sys
import os
from dotenv import load_dotenv
load_dotenv()

import imaplib
import email

from PyQt6.QtWidgets import QApplication, QMainWindow, QStatusBar, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QTableWidget, QStackedWidget, QDialog, QLineEdit, QTextEdit, QPushButton, QTableWidgetItem
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QThread, QObject, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from smtplib import SMTP_SSL

from email.message import EmailMessage
from email.utils import parsedate_to_datetime
import re

class MailContentWorker(QObject):
    # send html to MainWindow 
    content_loaded = pyqtSignal(str) 

    def __init__(self, mail_id):
        super().__init__()
        self.mail_id = mail_id

    def run(self):
        try:
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
        
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)
        
        #right row
        self.manager_layout = QStackedWidget()
        self.page_overview = QWidget()
        self.page_overview_layout = QVBoxLayout()
        self.page_overview.setLayout(self.page_overview_layout)
        
        self.details = QWebEngineView()
        self.details.setMinimumHeight(400)
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.back_to_overview)
        
        self.page_details = QWidget()
        self.page_details_layout = QVBoxLayout()
        self.page_details.setLayout(self.page_details_layout)
        
        self.page_details_layout.addWidget(self.back_button)
        self.page_details_layout.addWidget(self.details)
        
        self.manager_layout.addWidget(self.page_overview)
        self.manager_layout.addWidget(self.page_details)
        
        content_layout = QVBoxLayout()
        content_layout.addWidget(self.manager_layout)
        self.overview = QTableWidget()
        self.overview.setColumnCount(3)
        self.overview.setHorizontalHeaderLabels(["Sender", "Subject", "Date Received"])
        self.overview.setRowCount(29)
        self.page_overview_layout.addWidget(self.overview)

        #mail content

        self.overview.cellClicked.connect(self.show_details)
        
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

    def on_mail_loaded(self, row, sender, subject, date, mail_id):
        self.overview.setItem(row, 0, QTableWidgetItem(sender))
        self.overview.setItem(row, 1, QTableWidgetItem(subject))
        self.overview.setItem(row, 2, QTableWidgetItem(date))
        self.mail_storage[row] = mail_id

    def show_details(self, row, column):
        mail_id = self.mail_storage.get(row)
        self.manager_layout.setCurrentIndex(1)
        if not mail_id:
            return

        self.details.setHtml("<h3>⏳ Lade E-Mail-Inhalt...</h3>")

        self.content_worker = MailContentWorker(mail_id)
        self.content_thread = QThread()
        
        self.content_worker.moveToThread(self.content_thread)
        
        self.content_thread.started.connect(self.content_worker.run)
        self.content_worker.content_loaded.connect(self.display_content) 
        
        self.content_worker.content_loaded.connect(self.content_thread.quit)
        self.content_worker.content_loaded.connect(self.content_worker.deleteLater)
        self.content_thread.finished.connect(self.content_thread.deleteLater)

        self.content_thread.start()

    def display_content(self, html_content):
        self.details.setHtml(html_content)
    
    def back_to_overview(self):
        self.manager_layout.setCurrentIndex(0)
        
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
    mail_loaded = pyqtSignal(int, str, str, str, str)
    
    def get_local_formated_date(self, date_str):
        if not date_str:
            return None
        
        cleaned_str = re.sub(r'^[^0-9]*', '', date_str)
        
        try:
            dt = parsedate_to_datetime(cleaned_str)
            dt_local = dt.astimezone()
            return dt_local.strftime("%H:%M:%S %d.%m.%y")
        except Exception as e:
            print(f'Error while formatting date str: {date_str} with error: {e}')
            return None
            
    def run(self):
        with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
            mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
            mail_server.select("INBOX")
            #search all mails
            status, data = mail_server.search(None, "ALL")
            mail_ids = data[0].split()
            mail_ids.reverse()
            id_string = b",".join(mail_ids).decode()
            
            status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER)")

            for item in fetch_data:
                if isinstance(item, tuple):
                    loaded_msg = email.message_from_bytes(item[1])
                    
                    loaded_sender = loaded_msg["From"]
                    loaded_subject = loaded_msg["Subject"]
                    loaded_date = loaded_msg["Date"]

                    formated_date = self.get_local_formated_date(loaded_date)

                    msg_num = item[0].split()[0]
                    mail_id_str = msg_num.decode()
                    row_index = mail_ids.index(msg_num)
                    self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, formated_date, mail_id_str)


        
app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()