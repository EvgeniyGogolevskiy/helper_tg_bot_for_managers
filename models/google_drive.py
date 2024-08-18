import logging
import os
import urllib.request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from typing import NoReturn, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class GoogleAPI:
    """
    A class responsible for authorization and creation of Google API client.

    Attributes:
        _credentials_json_path (str | os.PathLike): path to google credentials json file.
        _scopes (list[str]): list of Google Drive scopes for service account. Default is GoogleAPI SCOPES.
        build (Callable[[], str]): Contains googleapiclient build() function.
         Default is None, defines in _get_service method.
        credentials (service_account.Credentials): Instance of the class Credentials.
         Default is None, defines in _get_credentials method.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.appdata",
        "https://www.googleapis.com/auth/drive.metadata",
    ]

    def __init__(self, credentials_path: str | os.PathLike, scopes: list[str] = SCOPES):
        self.credentials = None
        self.build = None
        self._credentials_json_path = credentials_path
        self._scopes = scopes

    def _get_credentials(self) -> service_account.Credentials:
        """
        Return an instance of the class Credentials for _get_service method.
        """

        self.credentials = service_account.Credentials.from_service_account_file(
            filename=self._credentials_json_path, scopes=self._scopes
        )
        return self.credentials

    def _get_service(self, service_name: str = "drive", version: str = "v3") -> Any:
        """
        Forming Google api client. Returns Resource object with methods for interacting with the service.

        Args:
            service_name (str): Name of Google service api.
            version (str): Service version.
        """
        self.build = build(
            service_name,
            version,
            credentials=self._get_credentials(),
            cache_discovery=False,
        )
        return self.build


class GoogleDrive(GoogleAPI):
    """
    A class with Google Drive api methods, inherits from the GoogleAPI.
    """

    def __init__(self, credentials_path: str | os.PathLike):
        super().__init__(credentials_path)

    def create_folder(
        self, folder_name: str, parent_id: str = "1BLiQ7HEyzhQwWIM0o_llVlgm1rScX4Ik"
    ) -> str:
        """
        Create folder on Google Drive.

        Args:
            folder_name (str): Folder name on Google Drive, like an organization name.
            parent_id (str): Drive ID of the folder in which it is located.
        """
        try:
            service = self._get_service()
            file_metadata = {
                "name": folder_name,
                "parents": [parent_id],
                "mimeType": "application/vnd.google-apps.folder",
            }

            file = service.files().create(body=file_metadata, fields="id").execute()
            logging.info(f'Folder has been created ID: "{file.get("id")}".')
            return file.get("id")
        except HttpError as err:
            logging.error(f"An error occurred in create folder process: {err}")
            return None

    def upload_foto_in_spec_folder(
        self, folder_id: str, url: str, drive_name_photo: str
    ) -> str:
        """
        Upload file in specified Google Drive folder.

        Args:
            folder_id (str): Google Drive parent folder id.
            url (str): photo URL path.
            drive_name_photo (str): photo file name on Google Drive.
        """

        file_name = f"{drive_name_photo}.png"

        # Download photo by url
        try:
            urllib.request.urlretrieve(url, file_name)
        except Exception as ex:
            logging.error(f"Error in retrieve process {ex}")

        # Upload downloaded photo to Google Drive
        try:
            service = self._get_service()
            file_metadata = {"name": file_name, "parents": [folder_id]}
            media = MediaFileUpload(
                filename=file_name, mimetype="image/jpeg", resumable=True
            )
            file = (
                service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            return file.get("id")
        except HttpError as error:
            logging.error(f"An error occurred in upload photo process: {error}")
            return None

    def search_folder(self, folder_name: str) -> str:
        """
        Search folder on Google Drive by name.

        Args:
            folder_name (str): Name of the folder to be searched.
        """

        try:
            service = self._get_service()
            page_token = None
            while True:
                # Response from Google Drive, page of objects list
                response = (
                    service.files()
                    .list(
                        q="mimeType='application/vnd.google-apps.folder'",
                        spaces="drive",
                        fields="nextPageToken, files(id, name)",
                        pageToken=page_token,
                    )
                    .execute()
                )

                # Find on page of objects list selected folder
                for file in response.get("files", []):
                    if file.get("name") == folder_name:
                        logging.info(
                            f'Found folder: {file.get("name")}, {file.get("id")}'
                        )
                        return file.get("id")

                # If folder not on current page, take next page
                page_token = response.get("nextPageToken", None)
                if page_token is None:
                    break
        except HttpError as error:
            logging.error(f"An error occurred in search folder: {error}")

        return None

    def upload_photo(self, folder_name: str, links: list[str]) -> NoReturn:
        """
        Upload photos to folder on Google Drive.

        Args:
            folder_name (str): Name of the folder where the photos will be uploaded.
            links (list[str]): List of URL's path to photo.
        """

        # Counter for the numbers of photo in param: links
        counter = 0

        # Create or search folder on Google Drive
        folder_id = self.search_folder(folder_name)

        if not folder_id:
            folder_id = self.create_folder(folder_name)

        # Create photo name, upload and remove from storage photo
        for url in links:
            file_name = f"{folder_name}_{counter}"
            self.upload_foto_in_spec_folder(
                folder_id=folder_id, url=url, drive_name_photo=file_name
            )
            logging.info(f"{file_name}.png uploaded to {folder_name}")
            os.remove(f"{file_name}.png")
            logging.info(f"File: {file_name}.png has been deleted.")
            counter += 1
