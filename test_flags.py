import imaplib

import credentials

email_user, email_password = credentials.get_credentials()
if not email_user or not email_password:
    print("Error: No credentials stored in Keychain.")
else:
    print(f"Testing IMAP flags for {email_user}...")
    with imaplib.IMAP4_SSL("imap.gmail.com") as mail_server:
        mail_server.login(email_user, email_password)
        mail_server.select("INBOX")
        status, data = mail_server.search(None, "ALL")
        mail_ids = data[0].split()
        if mail_ids:
            # Fetch the last 5 emails for quick test
            target_ids = mail_ids[-5:]
            id_string = b",".join(target_ids).decode()
            status, fetch_data = mail_server.fetch(id_string, "(RFC822.HEADER FLAGS)")
            print(f"RAW FETCH_DATA LENGTH: {len(fetch_data)}")
            for idx, item in enumerate(fetch_data):
                if isinstance(item, tuple):
                    print(
                        f"Item {idx}: Tuple key type={type(item[0])}, value length={len(item[1])}"
                    )
                elif isinstance(item, bytes):
                    print(f"Item {idx}: Bytes value={item[:50]}")
        else:
            print("No emails found to test flags.")
