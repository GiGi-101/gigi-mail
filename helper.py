import os
from dotenv import load_dotenv
load_dotenv()

import re
from email.utils import parsedate_to_datetime
from email.message import EmailMessage

import time
import datetime

def get_local_formated_date(date_str):
    """
    Parses an email date header string and formats it to the local timezone format.
    
    Args:
        date_str (str): The raw Date header value from the email message.
        
    Returns:
        str: Formatted local datetime string (HH:MM:SS DD.MM.YY) or None if parsing fails.
    """
    if not date_str:
        return None

    # Remove any leading non-numeric characters (e.g. day names like 'Thu, ')
    cleaned_str = re.sub(r'^[^0-9]*', '', date_str)

    try:
        # Convert date string to datetime object and shift to the local timezone
        dt = parsedate_to_datetime(cleaned_str)
        dt_local = dt.astimezone()
        return dt_local.strftime("%H:%M:%S %d.%m.%y")
    except Exception as e:
        print(f'Error while formatting date str: {date_str} with error: {e}')
        return None

def extract_email_body(msg):
    """
    Traverses a MIME email message to extract and return the body content.
    Prioritizes HTML content if available, falling back to plain text.
    
    Args:
        msg (email.message.Message): The parsed email message object.
        
    Returns:
        str: Decoded content of the email body.
    """
    content = ""
    
    if msg.is_multipart():
        # Traverse through all MIME parts of a multipart email
        for part in msg.walk():
            # Prioritize HTML content for rich text rendering in QWebEngineView
            if part.get_content_type() == "text/html":
                content = part.get_payload(decode=True).decode(errors="ignore")
                break
    else:
        # For singlepart emails, directly decode payload
        content = msg.get_payload(decode=True).decode(errors="ignore")
    
    # Fallback to the main payload if content is still empty
    if not content:
        content = msg.get_payload(decode=True).decode(errors="ignore")
        
    return content

def create_email(sender, receiver, subject, body):
    """
    Builds and returns an EmailMessage object ready to be sent via SMTP.
    
    Args:
        sender (str): Email address of the sender.
        receiver (str): Email address of the recipient.
        subject (str): Email subject.
        body (str): Plain text body of the email.
        
    Returns:
        EmailMessage: Ready-to-send email message object.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.set_content(body)