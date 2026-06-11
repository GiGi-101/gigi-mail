import logging
import os

import keyring

SERVICE_NAME = "gigi-mail"

# Try to load .env as a legacy fallback
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def get_credentials():
    """
    Retrieves (email_user, email_password) from macOS Keychain.
    Falls back to environment variables (e.g. legacy .env) if not found in Keychain.
    If credentials are found in environment variables but not in Keychain,
    migrates them to Keychain automatically.
    """
    try:
        email_user = keyring.get_password(SERVICE_NAME, "username")
        if email_user:
            email_password = keyring.get_password(SERVICE_NAME, email_user)
            if email_password:
                return email_user, email_password
    except Exception as e:
        logging.error(f"Failed to retrieve credentials from keyring: {e}")

    # Fallback to environment variables
    env_user = os.getenv("EMAIL_USER")
    env_password = os.getenv("EMAIL_PASSWORD")

    if env_user and env_password:
        logging.info(
            "Credentials found in environment variables. Migrating to Keychain..."
        )
        if set_credentials(env_user, env_password):
            logging.info("Credentials migrated successfully.")
        return env_user, env_password

    return None, None


def set_credentials(email_user, email_password):
    """
    Saves the email address and password to the OS Keychain.
    """
    try:
        # First save the username indicator
        keyring.set_password(SERVICE_NAME, "username", email_user)
        # Then save the actual password under that username
        keyring.set_password(SERVICE_NAME, email_user, email_password)
        return True
    except Exception as e:
        logging.error(f"Failed to save credentials to keyring: {e}")
        return False


def clear_credentials():
    """
    Removes credentials from the OS Keychain.
    """
    try:
        email_user = keyring.get_password(SERVICE_NAME, "username")
        if email_user:
            try:
                keyring.delete_password(SERVICE_NAME, email_user)
            except Exception:
                pass
        try:
            keyring.delete_password(SERVICE_NAME, "username")
        except Exception:
            pass
        return True
    except Exception as e:
        logging.error(f"Failed to clear credentials from keyring: {e}")
        return False


if __name__ == "__main__":
    # Self-test code
    logging.basicConfig(level=logging.INFO)
    print("Testing keyring module...")
    user, pwd = get_credentials()
    print(f"Current stored user: {user}")
    if user:
        print("Credentials retrieved successfully.")
    else:
        print("No credentials stored yet.")
