import email
import imaplib

import credentials


class ReceiveMail:
    def __init__(self):
        super().__init__()

    def load(self):
        email_user, email_password = credentials.get_credentials()
        if not email_user or not email_password:
            print("Error: No credentials stored in Keychain.")
            return

        print(f"Connecting as {email_user} to fetch latest mail...")
        with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
            mail_server.login(email_user, email_password)
            mail_server.select("INBOX")
            # search all mails
            status, data = mail_server.search(None, "ALL")
            mail_ids = data[0].split()
            if not mail_ids:
                print("No emails found.")
                return
            # get latest mail
            latest_id = mail_ids[-1]
            status, mail_data = mail_server.fetch(latest_id, "(RFC822)")
            msg = email.message_from_bytes(mail_data[0][1])
            print("Subject of latest email:")
            print(msg.get("Subject"))


my_client = ReceiveMail()
my_client.load()
