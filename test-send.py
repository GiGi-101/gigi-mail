from smtplib import SMTP_SSL
from email.message import EmailMessage
import os
from dotenv import load_dotenv
load_dotenv()

class mail():
    def __init__(self):
        super().__init__()
    
    def send(self):
        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg["From"] = "EMAIL_USER"
        msg["To"] = "EMAIL_USER"
        msg.set_content("Das ist ein Test")
        
        with SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)
            
my_client = mail()

my_client.send()