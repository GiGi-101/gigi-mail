import email
import email.policy
import imaplib
import logging

from PyQt6.QtCore import QObject, pyqtSignal

import credentials
from helper import extract_email_body, get_local_formated_date


def _normalize_folder(folder: str) -> str:
    if folder.lower() == "sent":
        return "[Gmail]/Sent Mail"
    if " " in folder and not (folder.startswith('"') and folder.endswith('"')):
        return f'"{folder}"'
    return folder


class IMAPAuthWorker(QObject):
    """Worker that verifies credentials by attempting a Gmail IMAP login."""

    finished = pyqtSignal(bool, str)

    def __init__(self, email_user, email_password):
        super().__init__()
        self.email_user = email_user
        self.email_password = email_password

    def run(self):
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as server:
                server.login(self.email_user, self.email_password)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class MailContentWorker(QObject):
    """Fetches the HTML or text body of a specific email."""

    content_loaded = pyqtSignal(str)

    def __init__(self, mail_id, folder="Inbox"):
        super().__init__()
        self.mail_id = mail_id
        self.folder = folder

    def run(self):
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                email_user, email_password = credentials.get_credentials()
                mail_server.login(email_user, email_password)

                actual_folder = _normalize_folder(self.folder)

                status, select_data = mail_server.select(actual_folder)
                if status != "OK":
                    err = select_data[0].decode("utf-8", errors="ignore") if select_data else "Unknown error"
                    raise imaplib.IMAP4.error(f"SELECT failed: {err}")

                status, mail_data = mail_server.fetch(self.mail_id, "(RFC822)")
                if status != "OK":
                    err = mail_data[0].decode("utf-8", errors="ignore") if mail_data else "Unknown error"
                    raise imaplib.IMAP4.error(f"FETCH failed: {err}")

                loaded_msg = email.message_from_bytes(mail_data[0][1], policy=email.policy.default)
                self.content_loaded.emit(extract_email_body(loaded_msg))

        except Exception as e:
            logging.error(f"MailContentWorker error for mail {self.mail_id}: {e}", exc_info=True)
            self.content_loaded.emit(f"Fehler beim Laden: {e}")


class MailWorker(QObject):
    """
    Fetches folder listings and email headers from Gmail IMAP.
    Supports both initial load (last 50 messages) and incremental update polling.
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

    def _emit_fetch_items(self, fetch_data, mail_ids):
        for i in range(len(fetch_data) - 2, -1, -2):
            tuple_item = fetch_data[i]
            flags_item = fetch_data[i + 1]
            if not (isinstance(tuple_item, tuple) and isinstance(flags_item, bytes)):
                continue
            loaded_msg = email.message_from_bytes(tuple_item[1], policy=email.policy.default)
            msg_num = tuple_item[0].split()[0]
            is_read = b"\\seen" in flags_item.lower()
            try:
                row_index = mail_ids.index(msg_num)
            except ValueError:
                row_index = 0
            self.mail_loaded.emit(
                row_index,
                loaded_msg.get("From", "Unbekannt"),
                loaded_msg.get("Subject", "Kein Betreff"),
                get_local_formated_date(loaded_msg.get("Date", "")),
                msg_num.decode("utf-8", errors="ignore"),
                is_read,
            )

    def run(self):
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                email_user, email_password = credentials.get_credentials()
                mail_server.login(email_user, email_password)

                if self.load_folders:
                    status, folder_data = mail_server.list()
                    if status != "OK":
                        err = folder_data[0].decode("utf-8", errors="ignore") if folder_data else "Unbekannter Fehler"
                        self.error_occurred.emit(f"Ordnerliste konnte nicht abgerufen werden: {err}")
                        raise imaplib.IMAP4.error(err)

                    folders = []
                    for line in folder_data:
                        if not line:
                            continue
                        line_str = line.decode("utf-8", errors="ignore")
                        if "\\noselect" in line_str.lower():
                            continue
                        parts = line_str.split(' "/" ')
                        if len(parts) > 1:
                            folders.append(parts[-1].strip('"'))
                    self.folders_loaded.emit(folders)

                actual_folder = _normalize_folder(self.folder)

                status, select_data = mail_server.select(actual_folder)
                if status != "OK":
                    err = select_data[0].decode("utf-8", errors="ignore") if select_data else "Unbekannter Fehler"
                    self.error_occurred.emit(f"Ordner konnte nicht ausgewählt werden: {err}")
                    raise imaplib.IMAP4.error(err)

                status, data = mail_server.search(None, "ALL")
                if status != "OK":
                    err = data[0].decode("utf-8", errors="ignore") if data else "Unbekannter Fehler"
                    self.error_occurred.emit(f"Fehler bei der E-Mail-Suche: {err}")
                    raise imaplib.IMAP4.error(err)

                mail_ids = data[0].split()
                if not mail_ids:
                    logging.info(f"Keine E-Mails im Ordner '{actual_folder}' gefunden.")
                    return

                newest_mail_id = int(mail_ids[-1].decode("utf-8", errors="ignore"))

                if self.top_mail_id is None:
                    logging.info(f"Initialer Ladevorgang für Ordner '{actual_folder}' gestartet.")
                    target_ids = mail_ids[-50:]
                elif newest_mail_id > int(self.top_mail_id):
                    logging.info(f"Neue E-Mails in '{actual_folder}' gefunden! Neueste ID: {newest_mail_id}")
                    target_ids = [mid for mid in mail_ids if int(mid) > int(self.top_mail_id)]
                else:
                    logging.info(f"Keine neuen E-Mails in '{actual_folder}'.")
                    return

                id_string = b",".join(target_ids).decode("utf-8", errors="ignore")
                status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER FLAGS)")
                if status != "OK":
                    err = fetch_data[0].decode("utf-8", errors="ignore") if fetch_data else "Unbekannter Fehler"
                    self.error_occurred.emit(f"Fehler beim Laden der E-Mail-Header: {err}")
                    raise imaplib.IMAP4.error(err)

                self._emit_fetch_items(fetch_data, mail_ids)

        except Exception as e:
            logging.error(f"Fehler im MailWorker bei Ordner '{self.folder}': {e}", exc_info=True)
        finally:
            self.finished.emit()


class DeleteMailWorker(QObject):
    """Sets the \\Deleted flag on an email via IMAP."""

    finished = pyqtSignal(bool, str)

    def __init__(self, mail_id, folder="Inbox"):
        super().__init__()
        self.mail_id = mail_id
        self.folder = folder

    def run(self):
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
                email_user, email_password = credentials.get_credentials()
                mail_server.login(email_user, email_password)

                actual_folder = _normalize_folder(self.folder)

                status, _ = mail_server.select(actual_folder)
                if status != "OK":
                    raise Exception("Failed to select folder")

                status, _ = mail_server.store(self.mail_id, "+FLAGS", "\\Deleted")
                if status != "OK":
                    raise Exception("Failed to mark email as deleted")

                # expunge() is intentionally omitted to avoid breaking sequence numbers during concurrent ops
                self.finished.emit(True, "")
        except Exception as e:
            logging.error(f"Fehler beim Löschen der E-Mail {self.mail_id}: {e}", exc_info=True)
            self.finished.emit(False, str(e))
