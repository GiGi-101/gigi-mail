import sys
import os
from dotenv import load_dotenv
load_dotenv()

from PyQt6.QtWidgets import QApplication, QMainWindow, QStatusBar, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QTableWidget, QTextBrowser, QDialog, QLineEdit, QTextEdit, QPushButton
from PyQt6.QtGui import QAction
from smtplib import SMTP_SSL
from email.message import EmailMessage

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
        self.details = QTextBrowser()
        content_layout.addWidget(self.overview)
        content_layout.addWidget(self.details)
        
        main_layout.addLayout(content_layout)
        
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Bereit")
    
    def open_compose_dialog(self):
        dialog = ComposeDialog()
        dialog.exec()
        
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
        
app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()