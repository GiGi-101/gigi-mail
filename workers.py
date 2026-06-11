import os
import imaplib
import email
import email.policy
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from helper import get_local_formated_date, extract_email_body

class MailContentWorker(QObject):
    """
    Worker thread task for fetching the HTML or text body of a specific email.
    """
    content_loaded = pyqtSignal(str) 

    def __init__(self, mail_id, folder="Inbox"):
        super().__init__()
        self.mail_id = mail_id
        self.folder = folder

    def run(self):
        """
        Connects to IMAP, selects the active folder, and fetches the full email body.
        """
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
                
                # Normalize folder name for Gmail IMAP selection
                actual_folder = self.folder
                if actual_folder.lower() == "sent":
                    actual_folder = "[Gmail]/Sent Mail"
                
                # Double quote folder name if it contains spaces and is not already quoted
                if " " in actual_folder and not (actual_folder.startswith('"') and actual_folder.endswith('"')):
                    actual_folder = f'"{actual_folder}"'
                
                status, select_data = mail_server.select(actual_folder)
                if status != 'OK':
                    err_msg = f"SELECT command failed: {select_data[0].decode('utf-8', errors='ignore') if select_data else 'Unknown error'}"
                    raise imaplib.IMAP4.error(err_msg)
                
                status, mail_data = mail_server.fetch(self.mail_id, "(RFC822)")
                if status != 'OK':
                    err_msg = f"FETCH command failed: {mail_data[0].decode('utf-8', errors='ignore') if mail_data else 'Unknown error'}"
                    raise imaplib.IMAP4.error(err_msg)
                    
                loaded_msg = email.message_from_bytes(mail_data[0][1], policy=email.policy.default)

                # Extract content using the utility function from helper.py
                content = extract_email_body(loaded_msg)
                self.content_loaded.emit(content)

        except Exception as e:
            logging.error(f"Fehler im MailContentWorker beim Laden von Mail {self.mail_id}: {e}", exc_info=True)
            self.content_loaded.emit(f"Fehler beim Laden: {e}")

class MailWorker(QObject):
    """
    Worker task responsible for executing network requests to fetch folder lists,
    querying the server for new email IDs, and downloading email header contents.
    """
    mail_loaded = pyqtSignal(int, str, str, str, str, bool)
    finished = pyqtSignal()
    folders_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, folder="Inbox", load_folders=False):
        super().__init__()
        self.top_mail_id = None
        self.folder = folder
        self.load_folders = load_folders
    
    def run(self):
        """
        Establishes SSL connection to GMail IMAP. Queries directory structures,
        selects active folder, and pulls down headers for new/initial emails.
        """
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
                
                # Fetch directory listings from IMAP server if requested
                if self.load_folders:
                    status, folder_data = mail_server.list()
                    if status != 'OK':
                        err_msg = f"Ordnerliste konnte nicht abgerufen werden: {folder_data[0].decode('utf-8', errors='ignore') if folder_data else 'Unbekannter Fehler'}"
                        self.error_occurred.emit(err_msg)
                        raise imaplib.IMAP4.error(err_msg)
                        
                    folders = []
                    for line in folder_data:
                        if line:
                            line_str = line.decode('utf-8', errors='ignore')
                            # Exclude non-selectable folders from UI list (like "[Gmail]")
                            if "\\noselect" in line_str.lower():
                                continue
                            parts = line_str.split(' "/" ')
                            if len(parts) > 1:
                                folder_name = parts[-1].strip('"')
                                folders.append(folder_name)
                    self.folders_loaded.emit(folders)
                
                # Normalize folder selection path
                actual_folder = self.folder
                if actual_folder.lower() == "sent":
                    actual_folder = "[Gmail]/Sent Mail"
                    
                # Double quote folder name if it contains spaces and is not already quoted
                if " " in actual_folder and not (actual_folder.startswith('"') and actual_folder.endswith('"')):
                    actual_folder = f'"{actual_folder}"'
                    
                status, select_data = mail_server.select(actual_folder)
                if status != 'OK':
                    err_msg = f"Ordner konnte nicht ausgewählt werden: {select_data[0].decode('utf-8', errors='ignore') if select_data else 'Unbekannter Fehler'}"
                    self.error_occurred.emit(err_msg)
                    raise imaplib.IMAP4.error(err_msg)
                
                # Fetch message IDs
                status, data = mail_server.search(None, "ALL")
                if status != 'OK':
                    err_msg = f"Fehler bei der E-Mail-Suche: {data[0].decode('utf-8', errors='ignore') if data else 'Unbekannter Fehler'}"
                    self.error_occurred.emit(err_msg)
                    raise imaplib.IMAP4.error(err_msg)
                    
                mail_ids = data[0].split()
                if not mail_ids:
                    logging.info(f"Keine E-Mails im Ordner '{actual_folder}' gefunden.")
                    return

                newest_mail_id = int(mail_ids[-1].decode('utf-8', errors='ignore'))
                
                # Determine loading paths: First initialization vs dynamic update polling
                if self.top_mail_id is None:
                    logging.info(f"Initialer Ladevorgang für Ordner '{actual_folder}' gestartet.")
                    # Pull only the latest 50 emails to keep it fast
                    target_ids = mail_ids[-50:]
                    id_string = b",".join(target_ids).decode('utf-8', errors='ignore')
                    
                    status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER FLAGS)")    
                    if status != 'OK':
                        err_msg = f"Fehler beim Laden der E-Mail-Header: {fetch_data[0].decode('utf-8', errors='ignore') if fetch_data else 'Unbekannter Fehler'}"
                        self.error_occurred.emit(err_msg)
                        raise imaplib.IMAP4.error(err_msg)
                        
                    num_items = len(fetch_data)
                    for i in range(num_items - 2, -1, -2):
                        tuple_item = fetch_data[i]
                        flags_item = fetch_data[i + 1]
                        
                        if isinstance(tuple_item, tuple) and isinstance(flags_item, bytes):
                            loaded_msg = email.message_from_bytes(tuple_item[1], policy=email.policy.default)                    
                            loaded_sender = loaded_msg.get("From", "Unbekannt")
                            loaded_subject = loaded_msg.get("Subject", "Kein Betreff")
                            loaded_date = loaded_msg.get("Date", "")

                            formated_date = get_local_formated_date(loaded_date)
                            msg_num = tuple_item[0].split()[0]
                            mail_id_str = msg_num.decode('utf-8', errors='ignore')
                            is_read = b"\\seen" in flags_item.lower()
                            try:
                                row_index = mail_ids.index(msg_num)
                            except ValueError:
                                row_index = 0
                            self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, formated_date, mail_id_str, is_read)
                            
                elif newest_mail_id > int(self.top_mail_id):
                    logging.info(f"Neue E-Mails in '{actual_folder}' gefunden! Neueste ID: {newest_mail_id}")
                    # Filter IDs to fetch headers only for newly arrived emails
                    new_ids = [mid for mid in mail_ids if int(mid) > int(self.top_mail_id)]
                    id_string = b",".join(new_ids).decode('utf-8', errors='ignore')
                    
                    status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER FLAGS)")
                    if status != 'OK':
                        err_msg = f"Fehler beim Laden neuer E-Mail-Header: {fetch_data[0].decode('utf-8', errors='ignore') if fetch_data else 'Unbekannter Fehler'}"
                        self.error_occurred.emit(err_msg)
                        raise imaplib.IMAP4.error(err_msg)
                        
                    num_items = len(fetch_data)
                    for i in range(num_items - 2, -1, -2):
                        tuple_item = fetch_data[i]
                        flags_item = fetch_data[i + 1]
                        
                        if isinstance(tuple_item, tuple) and isinstance(flags_item, bytes):
                            loaded_msg = email.message_from_bytes(tuple_item[1], policy=email.policy.default)                    
                            loaded_sender = loaded_msg.get("From", "Unbekannt")
                            loaded_subject = loaded_msg.get("Subject", "Kein Betreff")
                            loaded_date = loaded_msg.get("Date", "")

                            formated_date = get_local_formated_date(loaded_date)
                            msg_num = tuple_item[0].split()[0]
                            mail_id_str = msg_num.decode('utf-8', errors='ignore')
                            is_read = b"\\seen" in flags_item.lower()
                            try:
                                row_index = mail_ids.index(msg_num)
                            except ValueError:
                                row_index = 0
                            self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, formated_date, mail_id_str, is_read)
                else:
                    logging.info(f"Keine neuen E-Mails in '{actual_folder}'.")
                    
        except Exception as e:
            logging.error(f"Fehler im MailWorker bei Ordner '{self.folder}': {e}", exc_info=True)
        finally:
            self.finished.emit()

