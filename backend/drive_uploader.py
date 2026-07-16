import os
import asyncio
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from notion_client import Client as NotionClient

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")  # StudyFrame root folder
NOTION_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")  # StudyFrame study log DB

class DriveUploader:
    def __init__(self):
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        self.drive_service = build("drive", "v3", credentials=credentials)
        self.notion = NotionClient(auth=NOTION_TOKEN) if NOTION_TOKEN else None

    async def upload(self, video_path: str, question: str, job_id: str) -> dict:
        """
        Upload the MP4 to Google Drive and log the entry to Notion.
        Returns dict with drive_url and notion_url.
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._do_upload, video_path, question, job_id
        )
        return result

    def _do_upload(self, video_path: str, question: str, job_id: str) -> dict:
        """Synchronous upload (run in thread pool)."""
        result = {"drive_url": "", "notion_url": ""}

        # --- Upload to Google Drive ---
        try:
            filename = f"StudyFrame_{job_id[:8]}.mp4"
            file_metadata = {
                "name": filename,
                "parents": [DRIVE_FOLDER_ID] if DRIVE_FOLDER_ID else [],
                "mimeType": "video/mp4"
            }
            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                resumable=True,
                chunksize=5 * 1024 * 1024  # 5MB chunks
            )
            uploaded = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink, webContentLink"
            ).execute()

            file_id = uploaded.get("id")

            # Make the file accessible via link
            self.drive_service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"}
            ).execute()

            result["drive_url"] = uploaded.get("webViewLink", "")

        except Exception as e:
            result["drive_url"] = f"Upload failed: {str(e)}"

        # --- Log to Notion database ---
        if self.notion and NOTION_DB_ID:
            try:
                notion_page = self.notion.pages.create(
                    parent={"database_id": NOTION_DB_ID},
                    properties={
                        "Question": {
                            "title": [{"text": {"content": question[:2000]}}]
                        },
                        "Job ID": {
                            "rich_text": [{"text": {"content": job_id}}]
                        },
                        "Date": {
                            "date": {"start": datetime.now().isoformat()}
                        },
                        "Video URL": {
                            "url": result["drive_url"] or "pending"
                        },
                        "Status": {
                            "select": {"name": "Complete"}
                        }
                    }
                )
                result["notion_url"] = notion_page.get("url", "")
            except Exception as e:
                result["notion_url"] = f"Notion log failed: {str(e)}"

        return result
