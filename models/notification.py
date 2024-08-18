import datetime
import io
import logging
import os
import re
import gspread
import pandas as pd
import requests
from gspread.worksheet import Worksheet
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from typing import NoReturn, Any
from urllib.parse import urlparse, parse_qs
from haversine import haversine
from core.db_functions import get_maps_filtered_rows

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
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
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


class GoogleServices(GoogleAPI):
    """
    A class to manage interactions with Google Sheets via the Google Sheets API.

    Attributes:
        credentials_path (str | os.PathLike): Path to the service account credentials json file.
         Defaults is to_gitlab_google_acc.json
        sheets_url (str): URL of the Google Sheet to interact with.
        sheet (gspread.models.Worksheet): The worksheet object representing the Google Sheet.
    """

    def __init__(
        self,
        sheets_url: str,
        credentials_path: str | os.PathLike = "models/to_gitlab_google_acc.json",
    ) -> None:
        """
        Initializes the GoogleServices instance with the URL of the Google Sheet to interact with.

        Args:
            sheets_url (str): URL of the Google Sheet to interact with.
        """
        super().__init__(credentials_path)
        self.sheets_url = sheets_url
        self.sheet = self.init_google_sheets()

    def init_google_sheets(self) -> Worksheet:
        """
        Initializes the connection to the Google Sheet and returns the worksheet object.

        Returns:
            gspread.models.Worksheet: The worksheet object representing the Google Sheet.
        """
        try:
            creds = self._get_credentials()

            logging.info("Credentials loaded successfully.")
            client = gspread.authorize(creds)
            logging.info("Authorized with Google Sheets API.")

            sheet = client.open_by_url(self.sheets_url).sheet1
            return sheet
        except Exception as e:
            logging.error(f"Error initializing Google Sheets: {e}")

    def read_from_google_sheets(self) -> pd.DataFrame:
        """
        Reads data from the Google Sheet and returns it as a pandas DataFrame.

        Returns:
            pd.DataFrame: The data from the Google Sheet as a pandas DataFrame.
        """
        data = self.sheet.get_all_values()
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        logging.info("DataFrame created successfully.")
        return df

    @staticmethod
    def search_name_in_df(df: pd.DataFrame, name: str) -> tuple:
        """
        Searches for a name in the DataFrame and either returns the matching row or creates a new one if none exists.

        Args:
            df (pd.DataFrame): The DataFrame to search in.
            name (str): The name to search for.

        Returns:
            tuple: A tuple containing the matching row as a dictionary and a boolean indicating whether a new row was created.
        """
        created_new = False
        matches = df[df["name"] == name]
        if matches.empty:
            # Reading column names from the existing DataFrame
            column_names = df.columns
            # Creating a dictionary where all values are None except one
            new_row = {col: None for col in column_names}
            new_row["name"] = name
            created_new = True
            new_row_df = pd.DataFrame([new_row])
            new_row_df["ID"] = "№" + str(len(df) + 310)
            matches = new_row_df
            df = pd.concat([df, new_row_df], ignore_index=True)
            logging.info(f"No organization, record created {name}")

        output = matches[
            [
                "name",
                "type",
                "photos",
                "google_map",
                "phone_numbers",
                "Whatsapp",
                "hours_of_operation",
                "ID",
            ]
        ].to_dict(orient="index")
        logging.info(f"Dictionary created:  {next(iter(output.values()))}")
        return (next(iter(output.values())), created_new)

    def write_on_google_sheets(self, organization: dict) -> dict:
        """
        Writes or updates an organization's data on a Google Sheet. This method checks if the
        organization already exists in the sheet based on an 'ID'. If it does, the method updates
        the existing row with new data provided in the 'organization' dictionary. If the ID is not
        found, it adds a new row with the organization's data.

        Args:
            organization (dict): The organization's data to write or update. The dictionary must
                                include an 'ID' key to identify the organization's row in the sheet.

        Returns:
            dict: A dictionary containing the original values of the row that was updated. If a new row
                was added, it returns the values of the new row. If an error occurs during the operation,
                it returns False.

        Raises:
            Exception: Logs an exception if an error occurs during the sheet update process.

        """
        try:
            headers = self.sheet.row_values(1)
            data = self.sheet.get_all_records()

            existing_row_index = next(
                (
                    index
                    for index, row in enumerate(data, start=2)
                    if str(row.get("ID")) == str(organization.get("ID"))
                ),
                None,
            )

            if existing_row_index:
                # Read current values in this row
                current_values = self.sheet.row_values(existing_row_index)
                # Update values based on new data from the dictionary
                updated_values = [
                    organization.get(
                        header, current_values[idx] if idx < len(current_values) else ""
                    )
                    for idx, header in enumerate(headers)
                ]

                # Update the existing row with new data
                self.sheet.update(
                    f"A{existing_row_index}:{chr(64 + len(headers))}{existing_row_index}",
                    [updated_values],
                )
                logging.info(
                    f"Data successfully updated on Google Sheets at row {existing_row_index}: {updated_values}"
                )
                return dict(zip(headers, current_values))
            else:
                # Add a new row if ID is not found
                row_values = [organization.get(header, "") for header in headers]

                next_row_index = len(data) + 2
                cell_range = (
                    f"A{next_row_index}:{chr(64 + len(headers))}{next_row_index}"
                )

                # Use update method to insert the new row
                self.sheet.update(cell_range, [row_values])
                logging.info(
                    f"Data successfully added on Google Sheets at row {next_row_index} with values: {row_values}"
                )
                return dict(zip(headers, row_values))

        except Exception as e:
            logging.error(f"Error working with Google Sheets (WRITE): {e}")
            return False


class GoogleDrive(GoogleAPI):
    """
    A class with Google Drive api methods, inherits from the GoogleAPI.
    """

    def __init__(
        self, credentials_path: str | os.PathLike = "models/to_gitlab_google_acc.json"
    ):
        super().__init__(credentials_path)

    def create_folder(
        self, folder_name: str, parent_id: str = "1bbWI0NV_vyIV0uqS5qTB5H8UDzBbNFkb"
    ) -> str | None:
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
    ) -> str | None:
        """
        Upload file in specified Google Drive folder.

        Args:
            folder_id (str): Google Drive parent folder id.
            url (str): photo URL path.
            drive_name_photo (str): photo file name on Google Drive.
        """

        file_name = f"{drive_name_photo}.png"

        # Get a photo by url
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
        except requests.exceptions.HTTPError as errh:
            logging.error("HTTP Error while streaming process", errh.args[0])
            return None

        # Upload a photo while streaming to Google Drive
        try:
            service = self._get_service()
            file_metadata = {"name": file_name, "parents": [folder_id]}
            media = MediaIoBaseUpload(
                io.BytesIO(response.content), mimetype="image/jpeg"
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

    def search_folder(self, folder_name: str) -> str | None:
        """
        Search folder on Google Drive by name.

        Args:
            folder_name (str): Name of the folder to be searched.
        """

        try:
            service = self._get_service()
            page_token = None
            while True:
                # Response from Google Drive, page of object list
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

                # Find on page of object list selected folder
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

    def make_public_folder(self, folder_id) -> NoReturn:
        """
        Make public folder by folder Drive ID

        Args:
        folder_id (str): Google Drive folder ID
        """

        try:
            service = self._get_service()

            # Create permissions
            user_permissions = {"type": "anyone", "role": "reader"}
            service.permissions().create(
                fileId=folder_id, body=user_permissions, fields="id"
            ).execute()
            logging.info(f"Folder:{folder_id} is public")
        except HttpError as err:
            logging.error(
                f"An error occurred in sharing permissions folder process: {err}"
            )

    def upload_photo(self, folder_name: str, links: list[str]) -> str:
        """
        Upload photos to folder on Google Drive.

        Args:
            folder_name (str): Name of the folder where the photos will be uploaded.
            links (list[str]): List of URL's path to photo.
        """

        # Create or search folder on Google Drive
        folder_id = self.search_folder(folder_name)

        if not folder_id:
            folder_id = self.create_folder(folder_name)

        # Create photo name and upload
        for photo_link in links:
            date = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            file_name = f"{folder_name}_{date}"
            self.upload_foto_in_spec_folder(
                folder_id=folder_id, url=photo_link, drive_name_photo=file_name
            )
            logging.info(f"{file_name}.png uploaded to {folder_name}")

        self.make_public_folder(folder_id=folder_id)

        return f"https://drive.google.com/drive/folders/{folder_id}?usp=drive_link"


class GoogleMap:
    """
    A class to handle Google Maps URL operations, such as expanding shortened URLs
    and extracting coordinates.
    """

    @staticmethod
    def get_full_url(short_url: str) -> str:
        """
        Expands a shortened Google Maps URL to its full URL.

        Args:
            short_url (str): The shortened URL to expand.

        Returns:
            str: The expanded URL.
        """
        response = requests.head(short_url, allow_redirects=True)
        return response.url

    @staticmethod
    def extract_coordinates_google_maps(url: str) -> tuple[float, float] | None:
        """
        Extracts coordinates from a full Google Maps URL.

        Args:
            url (str): The Google Maps URL.

        Returns:
            tuple[float, float]: A tuple containing the latitude and longitude.
        """
        coordinates = []
        regex_pattern = r"(-?\d{1,2}\.\d{6}),(-?\d{1,2}\.\d{6})"
        parsed_url = urlparse(url)

        # Extract coordinates from the URL
        path_parts = parsed_url.path.split("/")
        for part in path_parts:
            if "@" in part:
                coordinates = part.split("@")[1].split(",")[:2]
            elif re.match(regex_pattern, part):
                coordinates = part.split(",")

            if coordinates:
                return float(coordinates[0]), float(coordinates[1])

        return None

    @staticmethod
    def get_coordinates_from_short_url(short_url: str) -> tuple[float, float]:
        """
        Expands a shortened Google Maps URL and extracts coordinates.

        Args:
            short_url (str): The shortened Google Maps URL.

        Returns:
            tuple[float, float]: A tuple containing the latitude and longitude.
        """
        full_url = GoogleMap.get_full_url(short_url)
        return GoogleMap.extract_coordinates_google_maps(full_url)

    def get_coordinates_from_link(self, url: str) -> Any | None:
        item_coordinates = None
        if url.startswith("https://"):
            if len(url) < 70:
                item_coordinates = self.get_coordinates_from_short_url(url)
            else:
                item_coordinates = self.extract_coordinates_google_maps(url)

        return item_coordinates

    def radius_list(
        self, longitude: float, latitude: float, radius: float, photo: str
    ) -> list | None:
        """
        Forming a venue list by radius, coordinates and photo existence.
        Args:
        longitude (float): part of user coordinates.
        latitude (float): part of user coordinates.
        radius (float): radius value around of user.
        photo (str): collecting parameter for this method, meaning return places with(out) photography.
        """
        radius_list = []
        user_coordinates = (longitude, latitude)

        places = get_maps_filtered_rows()
        for place in places:
            if place.coordinates and place.coordinates != "Bad url":
                place_coordinates = place.coordinates.replace(",", "").split()
                long, lat = [float(coord) for coord in place_coordinates]
                distance = haversine(user_coordinates, (long, lat))
                if distance <= radius:
                    if photo == "True":
                        if place.photo:
                            radius_list.append(
                                {
                                    "place_name": place.Name,
                                    "distance": distance,
                                    "id": place.ID,
                                }
                            )
                    elif photo == "False":
                        if not place.photo:
                            radius_list.append(
                                {
                                    "place_name": place.Name,
                                    "distance": distance,
                                    "id": place.ID,
                                }
                            )

        if radius_list:
            radius_list.sort(key=lambda x: x["distance"])
            for place in radius_list:
                name = place["place_name"]
                distance = place["distance"]

                if distance < 1:
                    distance = round(distance, 3)
                    message_distance = f"{distance * 1000} m"
                else:
                    distance = round(distance, 2)
                    message_distance = f"{distance} km"

                place.update({"message": f"{name} - {message_distance}"})
            return radius_list
        else:
            return None
