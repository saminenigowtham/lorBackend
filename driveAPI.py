

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
from googleapiclient.http import MediaIoBaseUpload
import io
from google.auth.transport.requests import Request
from google.oauth2 import service_account


# Google Drive API credentials
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'Credentials.json'

# Specify the folder ID where you want to upload the file
FOLDER_ID = '11SCCKU5wyoQ30HgqSRz-5siWXBIvuCpM'

# Function to authenticate with Google Drive API
def get_drive_service(SERVICE_ACCOUNT_FILE, SCOPES):
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

# Function to upload file to Google Drive
def upload_file_to_drive(file_path, file_name, FOLDER_ID, SCOPES , SERVICE_ACCOUNT_FILE ):
    drive_service = get_drive_service(SERVICE_ACCOUNT_FILE, SCOPES )

    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID]
    }

    media = MediaIoBaseUpload(io.FileIO(file_path, 'rb'), mimetype='application/pdf', resumable=True)

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    # Give read access to everyone
    permission = {
        'type': 'anyone',
        'role': 'reader'
    }
    drive_service.permissions().create(fileId=file['id'], body=permission).execute()

    return file['id']

