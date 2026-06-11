import sys
import os
from dotenv import load_dotenv
load_dotenv()

import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStatusBar, QWidget, QHBoxLayout, 
    QVBoxLayout, QListWidget, QTableWidget, QStackedWidget, QDialog, 
    QLineEdit, QTextEdit, QPushButton, QTableWidgetItem, QLabel, QMessageBox
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer, QThread
from PyQt6.QtWebEngineWidgets import QWebEngineView
from smtplib import SMTP_SSL

from helper import create_email, get_local_formated_date, extract_email_body
from workers import MailContentWorker, MailWorker

class MainWindow(QMainWindow):
    """
    Main application window hosting folders list, emails overview table,
    and the webview for email details. Handles thread instantiation and QTimer polling.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GiGi MAils")
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.resize(screen_geo.size())
        
        # Track active folder name and mail storage dynamically
        self.current_folder = "Inbox"
        self.mail_storage = {}
        self.top_mail_id = None
        
        self.init_ui()
        
    def init_ui(self):
        # Set up a polling timer to check for updates every 10 seconds
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.start_mail_loading)
        self.update_timer.start(10000)
        
        # Menu Bar
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
        
        # Main Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Folders List Widget (Left Pane)
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)
        self.list_widget.addItem("Inbox")
        self.list_widget.addItem("Sent")
        self.list_widget.currentTextChanged.connect(self.on_folder_changed)
        
        # Stacked Layout Manager for Right Pane (Overview vs. Detail view)
        self.manager_layout = QStackedWidget()
        self.page_overview = QWidget()
        self.page_overview_layout = QVBoxLayout()
        self.page_overview.setLayout(self.page_overview_layout)
        
        # Details Web View
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
        
        # Overview Table Widget
        self.overview = QTableWidget()
        self.overview.setColumnCount(3)
        self.overview.setHorizontalHeaderLabels(["Sender", "Subject", "Date Received"])
        self.overview.setRowCount(0)
        self.page_overview_layout.addWidget(self.overview)
        self.overview.cellClicked.connect(self.show_details)
        
        main_layout.addLayout(content_layout)
        
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Bereit")

        # Start initial email and folder loading
        self.start_mail_loading()

    def open_compose_dialog(self):
        """
        Opens the modal dialog to compose and send a new email.
        """
        dialog = ComposeDialog()
        dialog.exec()

    def populate_folders(self, folders):
        """
        Fills the list widget with folders fetched dynamically from the server.
        """
        self.list_widget.clear()
        for folder in folders:
            self.list_widget.addItem(folder)
        
    def start_mail_loading(self):
        """
        Launches the background worker to load or update emails for the active folder.
        Safely prevents thread overlapping if a network transaction is currently active.
        """
        if getattr(self, 'loading_thread', None) is not None and self.loading_thread.isRunning():
            print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}   | Ladevorgang läuft noch, überspringe dieses Intervall.')
            return
        
        # Determine loading state (First start vs Update check)
        self.is_updating = getattr(self, 'top_mail_id', None) is not None
        
        self.loading_thread = QThread()
        self.worker = MailWorker(self.current_folder)
        self.worker.top_mail_id = getattr(self, 'top_mail_id', None)
        self.worker.moveToThread(self.loading_thread)
        
        self.loading_thread.started.connect(self.worker.run)
        self.worker.mail_loaded.connect(self.on_mail_loaded)
        
        # Connect dynamic folder listing only once on startup
        if not self.is_updating:
            self.worker.folders_loaded.connect(self.populate_folders)
        
        # Thread/Worker lifetime management to prevent memory leaks
        self.worker.finished.connect(self.loading_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.loading_thread.finished.connect(self.loading_thread.deleteLater)
        self.loading_thread.finished.connect(lambda: setattr(self, 'loading_thread', None))
        
        self.loading_thread.start()

    def on_mail_loaded(self, row, sender, subject, date, mail_id):
        """
        Triggered when a new email header is fetched by the worker.
        Handles shifting the table indices if inserting a new mail at index 0.
        """
        if self.is_updating:
            # New emails should appear at the top. Shift keys in mail_storage dictionary.
            target_row = 0
            new_storage = {}
            for row_id, m_id in self.mail_storage.items():
                new_storage[row_id + 1] = m_id
            self.mail_storage = new_storage
        else:
            # Initial loading: Append emails chronologically to the end of the table
            target_row = self.overview.rowCount()
            
        current_count = target_row
        self.overview.insertRow(current_count)
        self.overview.setItem(current_count, 0, QTableWidgetItem(sender))
        self.overview.setItem(current_count, 1, QTableWidgetItem(subject))
        self.overview.setItem(current_count, 2, QTableWidgetItem(date))
        
        self.mail_storage[current_count] = mail_id
        self.top_mail_id = self.mail_storage[0]
        
    def show_details(self, row, column):
        """
        Transitions UI to details view and spawns MailContentWorker to load email body.
        """
        mail_id = self.mail_storage.get(row)
        self.manager_layout.setCurrentIndex(1)
        if not mail_id:
            return

        self.details.setHtml("<h3>⏳ Lade E-Mail-Inhalt...</h3>")

        self.content_worker = MailContentWorker(mail_id, self.current_folder)
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
    
    def on_folder_changed(self, folder_name):
        """
        Resets data storage and launches a reload operation when another folder is selected.
        """
        if not folder_name:
            return
        
        self.overview.setRowCount(0)
        self.mail_storage = {}
        self.top_mail_id = None
        self.current_folder = folder_name
        self.start_mail_loading()
        
class ComposeDialog(QDialog):
    """
    Modal window dialog to compose a new email message.
    """
    def __init__(self):
        super().__init__()
        dialog_layout = QVBoxLayout()
        l1 = QLabel("Receiver:")
        self.receiver = QLineEdit("joners.guenther@gmail.com")
        l2 = QLabel("Subject:")
        self.subject = QLineEdit()
        l3 = QLabel("Body:")
        self.text = QTextEdit()
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_mail)
        
        self.setLayout(dialog_layout)
        dialog_layout.addWidget(l1)
        dialog_layout.addWidget(self.receiver)
        dialog_layout.addWidget(l2)
        dialog_layout.addWidget(self.subject)
        dialog_layout.addWidget(l3)
        dialog_layout.addWidget(self.text)
        dialog_layout.addWidget(self.send_button)
        
    def send_mail(self):
        """
        Constructs the EmailMessage and sends it using SMTP_SSL.
        """
        msg = create_email(os.getenv("EMAIL_USER"), self.receiver.text(), self.subject.text(), self.text.toPlainText())
        
        try:
            with SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
                server.send_message(msg)
                self.accept() 
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Senden", f"Die E-Mail konnte nicht gesendet werden:\n{e}")
            print(f"Error while sending email: {e}")

if __name__ == "__main__":
    import signal
    # Enable Ctrl+C in terminal to terminate the application immediately
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()