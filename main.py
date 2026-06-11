import sys
import os
from dotenv import load_dotenv
load_dotenv()

import imaplib
import email

from PyQt6.QtWidgets import QApplication, QMainWindow, QStatusBar, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QTableWidget, QStackedWidget, QDialog, QLineEdit, QTextEdit, QPushButton, QTableWidgetItem, QLabel
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer, QThread, QObject, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from smtplib import SMTP_SSL

from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from helper import create_email, get_local_formated_date, extract_email_body

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

                content = extract_email_body(loaded_msg)

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
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.start_mail_loading)
        self.update_timer.start(10000)  # Alle 10 Sekunden überprüfen
        
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
        self.overview.setRowCount(0)
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
        self.worker.top_mail_id = getattr(self, 'top_mail_id', None)
        self.worker.moveToThread(self.loading_thread)
        
        self.loading_thread.started.connect(self.worker.run)
        self.worker.mail_loaded.connect(self.on_mail_loaded)
        
        #clean up worker
        self.worker.finished.connect(self.loading_thread.quit)                  #quit thread
        self.worker.finished.connect(self.worker.deleteLater)                   #delete from ram
        self.loading_thread.finished.connect(self.loading_thread.deleteLater)   #delete thread after stopping
        
        self.loading_thread.start()

    def on_mail_loaded(self, row, sender, subject, date, mail_id):
        if self.overview.rowCount() > 0 and getattr(self, "top_mail_id", None) is not None:
            target_row = 0
            new_storage = {}
            
            for row_id, m_id in self.mail_storage.items():
                new_storage[row_id+1] = m_id
            self.mail_storage = new_storage
        else:
            target_row = self.overview.rowCount()
            
        current_count = target_row
        self.overview.insertRow(current_count)
        self.overview.setItem(current_count, 0, QTableWidgetItem(sender))
        self.overview.setItem(current_count, 1, QTableWidgetItem(subject))
        self.overview.setItem(current_count, 2, QTableWidgetItem(date))
        
        self.mail_storage[current_count] = mail_id
        self.top_mail_id = self.mail_storage[0]
        
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
        l1 = QLabel()
        l2 = QLabel()
        l3 = QLabel()
        l4 = QLabel()
        
        self.setLayout(dialog_layout)
        l1.setText("Receiver:")
        self.receiver = QLineEdit("joners.guenther@gmail.com")
        l2.setText("Subject:")
        self.subject = QLineEdit()
        l3.setText("Body:")
        self.text = QTextEdit()
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_mail)
        dialog_layout.addWidget(l1)
        dialog_layout.addWidget(self.receiver)
        dialog_layout.addWidget(l2)
        dialog_layout.addWidget(self.subject)
        dialog_layout.addWidget(l3)
        dialog_layout.addWidget(self.text)
        dialog_layout.addWidget(self.send_button)
        
        
    def send_mail(self):
        msg =  create_email(os.getenv("EMAIL_USER"),self.receiver.text(),self.subject.text(),self.text.toPlainText()) #sender, receiver, subject, body
        
        with SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)
        
        self.accept()

class MailWorker(QObject):
    def __init__(self):
        super().__init__()
        self.top_mail_id = None
    
    mail_loaded = pyqtSignal(int, str, str, str, str)
    finished = pyqtSignal() # new signal
    
    def run(self):
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
                mail_server.select("INBOX")
                #search all mails
                status, data = mail_server.search(None, "ALL")
                mail_ids = data[0].split()
                newest_mail_id = int(mail_ids[-1].decode())
                if self.top_mail_id is None:
                    print(f'initial load')
                    target_ids = mail_ids[-15:]
                    id_string = b",".join(target_ids).decode()
                    status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER)")    
                    reversed_data = reversed(fetch_data)
                    
                    for item in reversed_data:
                            if isinstance(item, tuple):
                                loaded_msg = email.message_from_bytes(item[1])                    
                                loaded_sender = loaded_msg["From"]
                                loaded_subject = loaded_msg["Subject"]
                                loaded_date = loaded_msg["Date"]

                                formated_date = get_local_formated_date(loaded_date)

                                msg_num = item[0].split()[0]
                                mail_id_str = msg_num.decode()
                                row_index = mail_ids.index(msg_num)
                                self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, formated_date, mail_id_str)
                elif newest_mail_id > int(self.top_mail_id):
                        print(f"Neue E-Mails gefunden! Neueste ID: {newest_mail_id}")
                        new_ids = [mid for mid in mail_ids if int(mid) > int(self.top_mail_id)]
                        id_string = b",".join(new_ids).decode()
                        
                        status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER)")
                        reversed_data = reversed(fetch_data)
                        
                        for item in reversed_data:
                            if isinstance(item, tuple):
                                loaded_msg = email.message_from_bytes(item[1])                    
                                loaded_sender = loaded_msg["From"]
                                loaded_subject = loaded_msg["Subject"]
                                loaded_date = loaded_msg["Date"]

                                formated_date = get_local_formated_date(loaded_date)

                                msg_num = item[0].split()[0]
                                mail_id_str = msg_num.decode()
                                row_index = mail_ids.index(msg_num)
                                self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, formated_date, mail_id_str)
                else:
                    print("Keine neuen E-Mails.")
        except Exception as e:
                print(f"Fehler im MailWorker: {e}")
        finally:
            self.finished.emit()

        
import signal
# Enable Ctrl+C in terminal to terminate the application immediately
signal.signal(signal.SIGINT, signal.SIG_DFL)

app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()