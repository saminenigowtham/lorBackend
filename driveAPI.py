from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# Google Drive API credentials
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'Credentials.json'
# Specify the folder ID where you want to upload the file

# Function to authenticate with Google Drive API
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

# Function to upload file to Google Drive
def upload_file_to_drive(file_path, file_name, folder_id):
    drive_service = get_drive_service()

    file_metadata = {
        'name': file_name,
        'parents': [folder_id]  # Use the provided folder_id
    }

    # Determine the MIME type based on the file extension
    mime_type = 'application/octet-stream'  # Default MIME type
    if file_name.endswith('.pdf'):
        mime_type = 'application/pdf'
    elif file_name.endswith('.jpg') or file_name.endswith('.jpeg'):
        mime_type = 'image/jpeg'
    elif file_name.endswith('.png'):
        mime_type = 'image/png'
    # Add more MIME types as needed

    media = MediaIoBaseUpload(io.FileIO(file_path, 'rb'), mimetype=mime_type, resumable=True)

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