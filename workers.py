import os
import imaplib
import email
import datetime
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
                mail_server.select(actual_folder)
                
                status, mail_data = mail_server.fetch(self.mail_id, "(RFC822)")
                loaded_msg = email.message_from_bytes(mail_data[0][1])

                # Extract content using the utility function from helper.py
                content = extract_email_body(loaded_msg)
                self.content_loaded.emit(content)

        except Exception as e:
            self.content_loaded.emit(f"Fehler beim Laden: {e}")

class MailWorker(QObject):
    """
    Worker task responsible for executing network requests to fetch folder lists,
    querying the server for new email IDs, and downloading email header contents.
    """
    mail_loaded = pyqtSignal(int, str, str, str, str)
    finished = pyqtSignal()
    folders_loaded = pyqtSignal(list)

    def __init__(self, folder="Inbox"):
        super().__init__()
        self.top_mail_id = None
        self.folder = folder
    
    def run(self):
        """
        Establishes SSL connection to GMail IMAP. Queries directory structures,
        selects active folder, and pulls down headers for new/initial emails.
        """
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
                
                # Fetch directory listings from IMAP server
                status, folder_data = mail_server.list()
                folders = []
                for line in folder_data:
                    if line:
                        parts = line.decode().split(' "/" ')
                        if len(parts) > 1:
                            folder_name = parts[-1].strip('"')
                            folders.append(folder_name)
                self.folders_loaded.emit(folders)
                
                # Normalize folder selection path
                actual_folder = self.folder
                if actual_folder.lower() == "sent":
                    actual_folder = "[Gmail]/Sent Mail"
                mail_server.select(actual_folder)
                
                # Fetch message IDs
                status, data = mail_server.search(None, "ALL")
                mail_ids = data[0].split()
                if not mail_ids:
                    return

                newest_mail_id = int(mail_ids[-1].decode())
                
                # Determine loading paths: First initialization vs dynamic update polling
                if self.top_mail_id is None:
                    print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}   | initial load')
                    target_ids = mail_ids  # Pull all emails initially as requested
                    id_string = b",".join(target_ids).decode()
                    
                    status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER)")    
                    reversed_data = reversed(fetch_data)
                    
                    for item in reversed_data:
                        if isinstance(item, tuple):
                            loaded_msg = email.message_from_bytes(item[1])                    
                            loaded_sender = loaded_msg.get("From", "Unbekannt")
                            loaded_subject = loaded_msg.get("Subject", "Kein Betreff")
                            loaded_date = loaded_msg.get("Date", "")

                            formated_date = get_local_formated_date(loaded_date)
                            msg_num = item[0].split()[0]
                            mail_id_str = msg_num.decode()
                            row_index = mail_ids.index(msg_num)
                            self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, formated_date, mail_id_str)
                            
                elif newest_mail_id > int(self.top_mail_id):
                    print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}   | Neue E-Mails gefunden! Neueste ID: {newest_mail_id}')
                    # Filter IDs to fetch headers only for newly arrived emails
                    new_ids = [mid for mid in mail_ids if int(mid) > int(self.top_mail_id)]
                    id_string = b",".join(new_ids).decode()
                    
                    status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER)")
                    reversed_data = reversed(fetch_data)
                    
                    for item in reversed_data:
                        if isinstance(item, tuple):
                            loaded_msg = email.message_from_bytes(item[1])                    
                            loaded_sender = loaded_msg.get("From", "Unbekannt")
                            loaded_subject = loaded_msg.get("Subject", "Kein Betreff")
                            loaded_date = loaded_msg.get("Date", "")

                            formated_date = get_local_formated_date(loaded_date)
                            msg_num = item[0].split()[0]
                            mail_id_str = msg_num.decode()
                            row_index = mail_ids.index(msg_num)
                            self.mail_loaded.emit(row_index, loaded_sender, loaded_subject, formated_date, mail_id_str)
                else:
                    print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}   | Keine neuen E-Mails.')
                    
        except Exception as e:
            print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}   | Fehler im MailWorker: {e}')
        finally:
            self.finished.emit()
