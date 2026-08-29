import io
import json
import os
import tempfile

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

FOLDER_ID = "1q06oyJq5SXegTeRnl_CRY0_nbttX_P62"

TITLE = "The Luxury Lifestyle — The Life You Dream Of ✨"

DESCRIPTION = """Discover the luxurious lives of the rich and experience the lifestyle you dream of. ✨

Follow us for more amazing luxury videos!"""

CATEGORY_ID = "24"  # Entertainment
PRIVACY_STATUS = "public"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]

HISTORY_FILE = "uploaded.json"


def get_credentials():
    token_data = json.loads(os.environ["GOOGLE_TOKEN_JSON"])

    return Credentials.from_authorized_user_info(
        token_data,
        SCOPES
    )


def get_drive_service(credentials):
    return build("drive", "v3", credentials=credentials)


def get_youtube_service(credentials):
    return build("youtube", "v3", credentials=credentials)


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(history), f, indent=2)


def get_videos(drive):
    videos = []

    page_token = None

    while True:
        response = drive.files().list(
            q=(
                f"'{FOLDER_ID}' in parents "
                "and trashed = false "
                "and mimeType contains 'video/'"
            ),
            fields="nextPageToken, files(id,name,mimeType,size,createdTime)",
            pageSize=100,
            orderBy="createdTime asc",
            pageToken=page_token
        ).execute()

        videos.extend(response.get("files", []))

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return videos


def download_video(drive, file_id, filename):
    request = drive.files().get_media(fileId=file_id)

    with open(filename, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)

        done = False

        while not done:
            status, done = downloader.next_chunk()

            if status:
                print(
                    f"Download progress: "
                    f"{int(status.progress() * 100)}%"
                )


def upload_video(youtube, filename):
    body = {
        "snippet": {
            "title": TITLE,
            "description": DESCRIPTION,
            "categoryId": CATEGORY_ID,
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        filename,
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None

    while response is None:
        status, response = request.next_chunk()

        if status:
            print(
                f"Upload progress: "
                f"{int(status.progress() * 100)}%"
            )

    return response["id"]


def main():
    print("Starting Drive → YouTube uploader...")

    credentials = get_credentials()

    drive = get_drive_service(credentials)
    youtube = get_youtube_service(credentials)

    history = load_history()

    videos = get_videos(drive)

    print(f"Videos found in Drive folder: {len(videos)}")
    print(f"Already uploaded: {len(history)}")

    pending = [
        video for video in videos
        if video["id"] not in history
    ]

    if not pending:
        print("No new videos to upload.")
        return

    # Upload exactly ONE video per GitHub Actions run.
    video = pending[0]

    print(f"Next video: {video['name']}")
    print(f"Drive file ID: {video['id']}")

    with tempfile.TemporaryDirectory() as temp_dir:
        local_file = os.path.join(
            temp_dir,
            video["name"]
        )

        print("Downloading from Google Drive...")
        download_video(
            drive,
            video["id"],
            local_file
        )

        print("Uploading to YouTube...")
        youtube_id = upload_video(
            youtube,
            local_file
        )

        print(f"YouTube upload successful!")
        print(f"YouTube video ID: {youtube_id}")

    history.add(video["id"])
    save_history(history)

    print(f"Saved upload history for: {video['name']}")


if __name__ == "__main__":
    main()
