import os
from dotenv import load_dotenv
load_dotenv()

import re
from email.utils import parsedate_to_datetime
from email.message import EmailMessage

def get_local_formated_date(date_str):
    if not date_str:
        return None

    cleaned_str = re.sub(r'^[^0-9]*', '', date_str)

    try:
        dt = parsedate_to_datetime(cleaned_str)
        dt_local = dt.astimezone()
        return dt_local.strftime("%H:%M:%S %d.%m.%y")
    except Exception as e:
        print(f'Error while formatting date str: {date_str} with error: {e}')
        return None

def extract_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                content = part.get_payload(decode=True).decode(errors="ignore")
                break
    else:
        content = msg.get_payload(decode=True).decode(errors="ignore")
    
    if not content:
        content = msg.get_payload(decode=True).decode(errors="ignore")
    return content

def create_email(sender, receiver, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.set_content(body)
    print(f'msg: {msg}')
    return msg 