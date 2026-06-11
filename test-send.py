from email.message import EmailMessage
from smtplib import SMTP_SSL

import credentials


class mail:
    def __init__(self):
        super().__init__()

    def send(self):
        email_user, email_password = credentials.get_credentials()
        if not email_user or not email_password:
            print("Error: No credentials stored in Keychain.")
            return

        msg = EmailMessage()
        msg["Subject"] = "Test Secure Storage"
        msg["From"] = email_user
        msg["To"] = email_user
        msg.set_content(
            "Das ist ein Test über die sichere Schlüsselbund-Authentifizierung."
        )

        print(f"Sending test email from/to {email_user}...")
        with SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_password)
            server.send_message(msg)
        print("Email sent successfully!")


my_client = mail()
my_client.send()
