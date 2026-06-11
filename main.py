import sys
import os
import logging
from dotenv import load_dotenv
load_dotenv()

# Configure logging to write to both client.log and the console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("client.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStatusBar, QWidget, QHBoxLayout, 
    QVBoxLayout, QListWidget, QTableWidget, QStackedWidget, QDialog, 
    QLineEdit, QTextEdit, QPushButton, QTableWidgetItem, QLabel, QMessageBox,
    QHeaderView, QAbstractItemView, QStyledItemDelegate, QStyle
)
from PyQt6.QtGui import QAction, QColor, QFont, QBrush, QPen, QCursor
from PyQt6.QtCore import QTimer, QThread, Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView
from smtplib import SMTP_SSL

from helper import create_email, get_local_formated_date, extract_email_body, decode_imap_folder
from workers import MailContentWorker, MailWorker

class HoverTableWidget(QTableWidget):
    """
    Custom QTableWidget that tracks mouse movements and updates the hovered row
    to trigger repaint of row cells for a custom hover effect.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.hovered_row = -1
        
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        index = self.indexAt(event.position().toPoint())
        old_row = self.hovered_row
        if index.isValid():
            self.hovered_row = index.row()
        else:
            self.hovered_row = -1
            
        if self.hovered_row != old_row:
            self.viewport().update()
            
    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hovered_row = -1
        self.viewport().update()

class HoverDelegate(QStyledItemDelegate):
    """
    Custom delegate to style cells of the currently hovered row and draw a
    mechanical neon pink border around the row.
    """
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        view = self.parent()
        if hasattr(view, 'hovered_row') and view.hovered_row == index.row():
            # Apply hover background and text color styling only if not selected
            if not (option.state & QStyle.StateFlag.State_Selected):
                option.backgroundBrush = QBrush(QColor(255, 255, 255, 22))  # Translucent white
                option.palette.setColor(option.palette.ColorGroup.All, option.palette.ColorRole.Text, QColor("#ff007f"))
                option.palette.setColor(option.palette.ColorGroup.All, option.palette.ColorRole.HighlightedText, QColor("#ff007f"))
            
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        view = self.parent()
        if hasattr(view, 'hovered_row') and view.hovered_row == index.row():
            painter.save()
            pen = QPen(QColor(255, 0, 127, 180), 1)  # Translucent neon pink border
            painter.setPen(pen)
            
            rect = option.rect
            
            # Draw top and bottom borders
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
            
            # Draw left border for first column
            if index.column() == 0:
                painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
            
            # Draw right border for last column
            if index.column() == index.model().columnCount() - 1:
                painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
                
            painter.restore()



# Premium "Miami Vice + NFS Underground" Neon QSS Stylesheet
STYLESHEET = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #090611,
        stop:0.35 #1a0a2a,
        stop:0.7 #360b45,
        stop:1 #060e22);
}

/* Custom Translucent Scrollbars */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.12);
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.25);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.12);
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(255, 255, 255, 0.25);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}

/* Left Sidebar Folder Navigation */
QListWidget {
    background-color: rgba(255, 255, 255, 0.02);
    color: rgba(255, 255, 255, 0.85);
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    padding: 16px;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 15px;
}
QListWidget::item {
    padding: 12px 18px;
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 12px;
    margin-bottom: 8px;
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ff007f;
    border: 1px solid rgba(255, 0, 127, 0.4);
}
QListWidget::item:selected {
    background-color: rgba(255, 0, 127, 0.2);
    color: #ffffff;
    font-weight: bold;
    border: 1px solid rgba(255, 0, 127, 0.8);
}

/* Mail Overview Grid */
QTableWidget {
    background-color: rgba(255, 255, 255, 0.01);
    alternate-background-color: rgba(255, 255, 255, 0.03);
    color: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    gridline-color: rgba(255, 255, 255, 0.03);
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 15px;
}
QTableWidget::item {
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
QTableWidget::item:selected {
    background-color: rgba(0, 240, 255, 0.2);
    color: #ffffff;
    font-weight: bold;
}

QHeaderView::section {
    background-color: rgba(255, 255, 255, 0.04);
    color: #ff007f;
    padding: 12px 16px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-weight: bold;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

/* Web View container */
QWebEngineView {
    background-color: rgba(255, 255, 255, 0.01);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
}

/* Buttons style */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 rgba(255, 255, 255, 0.1),
                                stop:1 rgba(255, 255, 255, 0.03));
    color: #00f0ff;
    border: 1px solid rgba(0, 240, 255, 0.3);
    padding: 12px 24px;
    border-radius: 20px;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-weight: bold;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 rgba(0, 240, 255, 0.2),
                                stop:1 rgba(0, 240, 255, 0.05));
    color: #ffffff;
    border: 1px solid #00f0ff;
}
QPushButton:pressed {
    background-color: rgba(0, 240, 255, 0.35);
}

/* Status Bar */
QStatusBar {
    background-color: rgba(255, 255, 255, 0.02);
    color: #00f0ff;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 13px;
    padding: 6px;
}

/* Dialogs & Input fields */
QDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #100a1c,
        stop:0.5 #1d0f2b,
        stop:1 #0b0714);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
}
QLabel {
    color: #ff007f;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-weight: bold;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}
QLineEdit, QTextEdit {
    background-color: rgba(255, 255, 255, 0.03);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 15px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #ff007f;
    background-color: rgba(255, 255, 255, 0.05);
}
"""



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
        
        # Apply the global stylesheet to the main window
        self.setStyleSheet(STYLESHEET)
        
        # Track active folder name and mail storage dynamically
        self.current_folder = "Inbox"
        self.folders_map = {}  # Maps readable folder names to raw IMAP modified UTF-7 names
        self.mail_storage = {}
        self.top_mail_id = None
        self.folders_loaded_once = False
        
        # Track active background threads and workers to prevent overlaps and leaks
        self.active_threads = set()
        self.active_workers = set()
        
        self.init_ui()
        
    def init_ui(self):
        """Initializes the user interface and sets up the layout and polling timer."""
        # Set up a polling timer to check for updates every 10 seconds
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(lambda: self.start_mail_loading(force=False))
        self.update_timer.start(10000)
        
        self.setup_menu_bar()
        
        # Main Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        # Clean margins for modern edge-to-edge feel
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_widget.setLayout(main_layout)
        
        self.setup_sidebar(main_layout)
        self.setup_content_pane(main_layout)
        
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Bereit")

        # Start initial email and folder loading
        self.start_mail_loading(force=True)

    def setup_menu_bar(self):
        """Sets up the top menu bar actions and hotkeys."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        
        exit_action = QAction("Close the awesome client", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Anwendung schließen")
        exit_action.triggered.connect(self.close)
        
        new_mail_action = QAction("New Mail", self)
        new_mail_action.triggered.connect(self.open_compose_dialog)
        
        file_menu.addAction(exit_action)
        file_menu.addAction(new_mail_action)

    def setup_sidebar(self, parent_layout):
        """Sets up the mailbox folder list widget on the left sidebar."""
        self.list_widget = QListWidget()
        parent_layout.addWidget(self.list_widget, 1)  # Stretch factor 1
        self.list_widget.addItem("Inbox")
        self.list_widget.addItem("Sent")
        self.list_widget.currentTextChanged.connect(self.on_folder_changed)

    def setup_content_pane(self, parent_layout):
        """Sets up the right main pane with the stacked layout (overview & details)."""
        self.manager_layout = QStackedWidget()
        
        # Page 1: Overview
        self.page_overview = QWidget()
        self.page_overview_layout = QVBoxLayout()
        # Add a nice padding to the overview table
        self.page_overview_layout.setContentsMargins(15, 15, 15, 15)
        self.page_overview_layout.setSpacing(10)
        self.page_overview.setLayout(self.page_overview_layout)
        
        self.setup_overview_table()
        
        # Page 2: Details
        self.page_details = QWidget()
        self.page_details_layout = QVBoxLayout()
        self.page_details_layout.setContentsMargins(15, 15, 15, 15)
        self.page_details_layout.setSpacing(10)
        self.page_details.setLayout(self.page_details_layout)
        
        self.details = QWebEngineView()
        self.details.setMinimumHeight(400)
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.back_to_overview)
        
        # Back button wrapper layout to align left
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.back_button)
        button_layout.addStretch()
        
        self.page_details_layout.addLayout(button_layout)
        self.page_details_layout.addWidget(self.details)
        
        # Add to manager
        self.manager_layout.addWidget(self.page_overview)
        self.manager_layout.addWidget(self.page_details)
        
        content_layout = QVBoxLayout()
        content_layout.addWidget(self.manager_layout)
        parent_layout.addLayout(content_layout, 4)  # Stretch factor 4 (ratio 1:4 with sidebar)


    def setup_overview_table(self):
        """Sets up the table widget showing list of mails with modern grid options."""
        self.overview = HoverTableWidget()
        self.overview.setColumnCount(3)
        self.overview.setHorizontalHeaderLabels(["Sender", "Subject", "Date Received"])
        self.overview.setRowCount(0)
        
        # Hide the vertical row headers (numbers)
        self.overview.verticalHeader().setVisible(False)
        
        # Select entire rows, not individual cells
        self.overview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.overview.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Disable editing of cells
        self.overview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Configure columns stretch ratios
        header = self.overview.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Stretch Subject to take remaining space
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        
        # Initial default widths for columns
        self.overview.setColumnWidth(0, 240)
        self.overview.setColumnWidth(2, 200)
        
        # Set modern spacious row and header heights
        self.overview.verticalHeader().setDefaultSectionSize(55)
        self.overview.horizontalHeader().setMinimumHeight(50)
        
        # Alternating row colors for clean grid view
        self.overview.setAlternatingRowColors(True)
        
        self.overview.cellClicked.connect(self.show_details)
        
        # Set our custom hover delegate
        self.overview.setItemDelegate(HoverDelegate(self.overview))
        
        self.page_overview_layout.addWidget(self.overview)


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
        self.folders_loaded_once = True
        # Block signals so clear() and addItem() do not trigger currentTextChanged and cause infinite reload loops
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.folders_map.clear()
        
        for raw_folder in folders:
            readable_name = decode_imap_folder(raw_folder)
            self.folders_map[readable_name] = raw_folder
            self.list_widget.addItem(readable_name)
            
        # Find and re-select the currently active folder visually in the list
        readable_current = "Inbox"
        for readable, raw in self.folders_map.items():
            if raw == self.current_folder:
                readable_current = readable
                break
                
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.text() == readable_current:
                self.list_widget.setCurrentItem(item)
                break
                
        self.list_widget.blockSignals(False)
    def start_mail_loading(self, force=False):
        """
        Launches the background worker to load or update emails for the active folder.
        Safely prevents thread overlapping or cleans up previous signals if forced.
        """
        # Clean up already finished threads from our tracking set
        self.active_threads = {t for t in self.active_threads if t.isRunning()}
        
        # Check if any loading thread is currently running
        if not force and self.active_threads:
            logging.info("Ladevorgang läuft noch, überspringe dieses Intervall.")
            return
            
        # If forcing (e.g. folder changed), disconnect active workers from UI callbacks
        if force and self.active_threads:
            logging.info("Anderer Ordner gewählt, trenne Signale der laufenden Hintergrund-Worker.")
            for active_worker in list(self.active_workers):
                try:
                    active_worker.mail_loaded.disconnect(self.on_mail_loaded)
                except (TypeError, AttributeError):
                    pass
                try:
                    active_worker.folders_loaded.disconnect(self.populate_folders)
                except (TypeError, AttributeError):
                    pass
                try:
                    active_worker.error_occurred.disconnect(self.on_worker_error)
                except (TypeError, AttributeError):
                    pass
        
        # Determine loading state (First start vs Update check)
        self.is_updating = getattr(self, 'top_mail_id', None) is not None
        
        thread = QThread()
        worker = MailWorker(self.current_folder, load_folders=not self.folders_loaded_once)
        worker.top_mail_id = getattr(self, 'top_mail_id', None)
        worker.moveToThread(thread)
        
        self.active_threads.add(thread)
        self.active_workers.add(worker)
        
        thread.started.connect(worker.run)
        worker.mail_loaded.connect(self.on_mail_loaded)
        worker.error_occurred.connect(self.on_worker_error)
        
        # Connect dynamic folder listing only once on startup
        if not self.is_updating:
            worker.folders_loaded.connect(self.populate_folders)
        
        # Thread/Worker lifetime management to prevent memory leaks
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda w=worker: self.active_workers.discard(w))
        
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda t=thread: self.active_threads.discard(t))
        
        thread.start()

    def on_mail_loaded(self, row, sender, subject, date, mail_id, is_read):
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
        
        sender_item = QTableWidgetItem(sender)
        subject_item = QTableWidgetItem(subject)
        date_item = QTableWidgetItem(date)
        
        if not is_read:
            bold_font = QFont()
            bold_font.setBold(True)
            sender_item.setFont(bold_font)
            subject_item.setFont(bold_font)
            date_item.setFont(bold_font)
            
        self.overview.setItem(current_count, 0, sender_item)
        self.overview.setItem(current_count, 1, subject_item)
        self.overview.setItem(current_count, 2, date_item)
        
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

        # Disconnect previous content worker signals if still running to avoid UI display overlaps
        if getattr(self, 'content_thread', None) is not None and self.content_thread.isRunning():
            try:
                self.content_worker.content_loaded.disconnect(self.display_content)
            except (TypeError, AttributeError):
                pass

        # Protect content worker/thread from garbage collection by adding them to the tracking sets
        self.content_worker = MailContentWorker(mail_id, self.current_folder)
        self.content_thread = QThread()
        
        self.content_worker.moveToThread(self.content_thread)
        self.active_threads.add(self.content_thread)
        self.active_workers.add(self.content_worker)
        
        self.content_thread.started.connect(self.content_worker.run)
        self.content_worker.content_loaded.connect(self.display_content) 
        
        self.content_worker.content_loaded.connect(self.content_thread.quit)
        self.content_worker.content_loaded.connect(self.content_worker.deleteLater)
        self.content_worker.content_loaded.connect(lambda *args, w=self.content_worker: self.active_workers.discard(w))
        
        self.content_thread.finished.connect(self.content_thread.deleteLater)
        self.content_thread.finished.connect(lambda *args, t=self.content_thread: self.active_threads.discard(t))
        self.content_thread.finished.connect(lambda: setattr(self, 'content_thread', None))
        self.content_thread.finished.connect(lambda: setattr(self, 'content_worker', None))

        self.content_thread.start()

    def display_content(self, html_content):
        self.details.setHtml(html_content)
        
    def on_worker_error(self, message):
        """Displays error messages in the status bar."""
        logging.error(f"Worker-Fehler gemeldet: {message}")
        self.statusBar().showMessage(f"Fehler: {message}", 5000)
    
    def back_to_overview(self):
        self.manager_layout.setCurrentIndex(0)
    
    def on_folder_changed(self, folder_name):
        """
        Resets data storage and launches a reload operation when another folder is selected.
        """
        if not folder_name:
            return
        
        logging.info(f"Ordnerwechsel zu: {folder_name}")
        self.overview.setRowCount(0)
        self.mail_storage = {}
        self.top_mail_id = None
        # Retrieve the raw IMAP UTF-7 name from our mapping dictionary
        self.current_folder = self.folders_map.get(folder_name, folder_name)
        self.start_mail_loading(force=True)
        
class ComposeDialog(QDialog):
    """
    Modal window dialog to compose a new email message.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NEW TRANSMISSION // COMPOSE MAIL")
        self.resize(650, 750)
        
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(32, 32, 32, 32)
        dialog_layout.setSpacing(18)
        
        # Header title
        header_title = QLabel("CREATE NEW TRANSMISSION")
        header_title.setStyleSheet("font-size: 18px; color: #00f0ff; letter-spacing: 2px;")
        
        l1 = QLabel("> RECEIVER")
        self.receiver = QLineEdit("joners.guenther@gmail.com")
        self.receiver.setPlaceholderText("Enter receiver email address...")
        
        l2 = QLabel("> SUBJECT")
        self.subject = QLineEdit()
        self.subject.setPlaceholderText("Enter transmission subject...")
        
        l3 = QLabel("> MESSAGE BODY")
        self.text = QTextEdit()
        self.text.setPlaceholderText("Type your message here...")
        
        # Cancel and Send buttons aligned in a modern row layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)
        button_layout.addStretch()
        
        cancel_button = QPushButton("Abort")
        cancel_button.clicked.connect(self.reject)
        
        self.send_button = QPushButton("Transmit")
        self.send_button.clicked.connect(self.send_mail)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.send_button)
        
        dialog_layout.addWidget(header_title)
        dialog_layout.addWidget(l1)
        dialog_layout.addWidget(self.receiver)
        dialog_layout.addWidget(l2)
        dialog_layout.addWidget(self.subject)
        dialog_layout.addWidget(l3)
        dialog_layout.addWidget(self.text)
        dialog_layout.addLayout(button_layout)
        
        self.setLayout(dialog_layout)
        
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
            logging.error(f"Error while sending email: {e}", exc_info=True)

if __name__ == "__main__":
    import signal
    # Enable Ctrl+C in terminal to terminate the application immediately
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()