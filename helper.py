import os
import binascii
from dotenv import load_dotenv
load_dotenv()

import re
from email.utils import parsedate_to_datetime
from email.message import EmailMessage

import time
import datetime

def decode_imap_folder(s):
    """
    Decodes an IMAP mailbox folder name from modified UTF-7 (RFC 3501) to standard unicode.
    For example, 'Entw&APw-rfe' becomes 'Entwürfe'.
    
    Args:
        s (str): The raw folder name from the IMAP server.
        
    Returns:
        str: Decoded readable folder name.
    """
    res = []
    i = 0
    while i < len(s):
        if s[i] == '&':
            j = s.find('-', i)
            if j == -1:
                res.append(s[i:])
                break
            part = s[i+1:j]
            if not part:
                res.append('&')
            else:
                # IMAP modified UTF-7 uses comma instead of slash
                modified_b64 = part.replace(',', '/')
                # Add base64 padding if necessary
                pad = len(modified_b64) % 4
                if pad:
                    modified_b64 += '=' * (4 - pad)
                try:
                    utf16_bytes = binascii.a2b_base64(modified_b64)
                    decoded_part = utf16_bytes.decode('utf-16-be')
                    res.append(decoded_part)
                except Exception:
                    res.append(s[i:j+1])
            i = j + 1
        else:
            res.append(s[i])
            i += 1
    return "".join(res)

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
                charset = part.get_content_charset() or "utf-8"
                content = part.get_payload(decode=True).decode(charset, errors="ignore")
                break
    else:
        # For singlepart emails, directly decode payload
        charset = msg.get_content_charset() or "utf-8"
        content = msg.get_payload(decode=True).decode(charset, errors="ignore")
    
    # Fallback to the main payload if content is still empty
    if not content:
        charset = msg.get_content_charset() or "utf-8"
        content = msg.get_payload(decode=True).decode(charset, errors="ignore")
        
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
    print(f'Created email message: {msg["Subject"]}')
    return msg