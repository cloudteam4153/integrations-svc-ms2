
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest

from security import token_cipher
from config.settings import settings
import json
from email.message import EmailMessage
from email.utils import formatdate
import base64
import time
from pathlib import Path

def main():

    BASE_DIR = Path(__file__).resolve().parent

    # get credential info (access token, refresh token, etc)
    with open(BASE_DIR / "test_gmail_auth.json", "r", encoding="utf-8") as f:
        info = json.load(f)

    token_row = {
        "token": token_cipher.decrypt(info["token"]),
        "refresh_token": token_cipher.decrypt(info["refresh_token"]),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "scopes": info["scopes"],
        "expiry": info.get("expiry")  # optional but recommended
    }

    creds: Credentials = Credentials.from_authorized_user_info(token_row)

    # refresh credentials
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())

    # build email resource
    service = build("gmail", "v1", credentials=creds)

    # make sure we're not seeding a real email address
    profile = service.users().getProfile(userId="me").execute()
    email_addr = profile["emailAddress"]

    if "cloudprojecttest4153@gmail.com" not in email_addr.lower():
        raise RuntimeError("Cannot seed non-testing email.")


    # load emails
    with open(BASE_DIR / "gmail_seed_data.json", "r", encoding="utf-8") as f:
        emails = json.load(f)

    # iterate through JSON
    for email in emails:

        # generate email
        message = EmailMessage()
        message.set_content(email["body"])
        message["To"] = email["to"]
        message["From"] = email["from"]
        message["Subject"] = email["subject"]

        days_ago = int(email.get("days_ago", 0))
        backdate_unix_seconds = time.time() - (days_ago * 24 * 60 * 60)
        backdate_millis = str(int(backdate_unix_seconds * 1000))
        message["Date"] = formatdate(timeval=backdate_unix_seconds, usegmt=True)

        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()

        insert_body = {
            "raw": encoded,
            "labelIds": email.get("labels", ["INBOX"]),
            "internalDate": backdate_millis
        }

        service.users().messages().import_(
            userId="me",
            body=insert_body
        ).execute()

        print(f"Inserted: {email['subject']} ({days_ago} days ago)")

    print("Gmail seeding complete.")


if __name__ == "__main__":
    main()
