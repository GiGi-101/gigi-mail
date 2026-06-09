import imaplib
import os
import email
from dotenv import load_dotenv
load_dotenv()

class ReceiveMail():
    def __init__(self):
        super().__init__()
    
    def load(self):
        with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
            mail_server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
            mail_server.select("INBOX")
            #search all mails
            status, data = mail_server.search(None, "ALL")
            mail_ids = data[0].split()
            #get latest mail
            latest_id = mail_ids[-1]
            status, mail_data = mail_server.fetch(latest_id, "(RFC822)")
            msg = email.message_from_bytes(mail_data[0][1])
            print(msg)


my_client = ReceiveMail()
my_client.load()