import logging
import re
from typing import Any, Dict, List
from urllib.parse import urlparse
import requests
from notion_client import Client
from notion_client.helpers import collect_paginated_api
from config import NOTION_API_ID, NOTION_DATABASE_ID
import schedule
import time
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
from sqlalchemy import create_engine
from config import mysql_db_path

# from core.db_functions import put_coordinates
from core.model import ModelPlaceCard

# from models.google_services import GoogleMap

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Notion:
    def __init__(self, notion_api_id: str, notion_database_id: str) -> None:
        """Initializes the Notion client with API ID and database ID.

        Args:
            notion_api_id (str): The API ID for Notion.
            notion_database_id (str): The database ID for Notion.
        """
        self.client = Client(auth=notion_api_id)
        self.database_id = notion_database_id
        logging.info("Initialized Notion client with API ID and database ID.")

    def read_all_rows(self) -> List[Dict[str, Any]]:
        """Reads all rows from the Notion database.

        Returns:
        List[Dict[str, Any]]: A list of dictionaries representing rows in the database.
        """
        logging.debug(f"Querying all rows from database ID: {self.database_id}")
        try:
            rows = collect_paginated_api(
                self.client.databases.query, database_id=self.database_id
            )
            logging.info(f"Retrieved {len(rows)} rows from the database.")
            return rows
        except Exception as e:
            logging.error(f"Error reading rows from database: {e}")
            raise

    def update_or_insert_row(
        self, row_id: str, row_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Updates an existing row or inserts a new row into the Notion database.

        Args:
            row_id (str): The ID of the row to update or create.
            row_data (Dict[str, Any]): A dictionary where keys are column names and values are data to insert or update.

        Returns:
            Dict[str, Any]: The response from the Notion API after creating or updating the row.
        """
        logging.debug(
            f"Updating or inserting a row in the database ID: {self.database_id} with ID: {row_id} and data: {row_data}"
        )
        try:
            rows = self.read_all_rows()
            existing_row = next((row for row in rows if row["id"] == row_id), None)

            properties = {}
            for column_name, value in row_data.items():
                properties[column_name] = self.format_property(column_name, value)

            if existing_row:
                # Update existing row
                response = self.client.pages.update(
                    page_id=row_id, properties=properties
                )
                logging.info(
                    f"Updated row in the notion database: {response.get('id')}"
                )
            else:
                # Create new row
                new_row = {
                    "parent": {"database_id": self.database_id},
                    "properties": properties,
                }
                response = self.client.pages.create(**new_row)
                logging.info(
                    f"Inserted new row into the notion database: {response.get('id')}"
                )

            return response
        except Exception as e:
            logging.error(f"Error updating or inserting row into notion database: {e}")
            raise

    def format_property(self, column_name: str, value: Any) -> Dict[str, Any]:
        """Formats a property for insertion into Notion.

        Args:
            column_name (str): The name of the column.
            value (Any): The value to format.

        Returns:
            Dict[str, Any]: The formatted property.
        """
        logging.debug(
            f"Formatting property for column: {column_name} with value: {value}"
        )
        if column_name == "Name":
            return {"title": [{"type": "text", "text": {"content": value}}]}
        elif column_name == "Photo Google Drive" or column_name == "Google Map":
            return {"url": value}

        elif column_name == "Type":
            return {"select": {"name": value}}

        elif (
            column_name == "Phone Number"
            or column_name == "WhatsApp Number"
            or column_name == "Hours of Operation"
            or column_name == "Phone Number"
            or column_name == "Owner / Manager"
        ):
            return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

        elif isinstance(value, str):
            return {"rich_text": [{"type": "text", "text": {"content": value}}]}
        elif isinstance(value, list):
            return {"multi_select": [{"name": val} for val in value]}
        elif isinstance(value, bool):
            return {"checkbox": value}
        elif isinstance(value, int):
            return {"number": value}
        elif isinstance(value, dict):
            return {"select": {"name": value["name"]}}
        else:
            return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

    def sync(self) -> None:
        """
        Start the synchronization process.
        This function sets up a scheduled task to run every 30 seconds.
        """
        logging.info("Start sync")
        engine = create_engine(mysql_db_path)
        Session = sessionmaker(bind=engine)
        schedule.every(15).seconds.do(self._scheduled_task_to_Notion, Session=Session)
        schedule.every(30).seconds.do(self._scheduled_task_from_Notion, Session=Session)
        logging.info("End sync")
        while True:
            schedule.run_pending()
            time.sleep(1)

    def _scheduled_task_to_Notion(self, Session: SQLAlchemySession) -> None:
        """
        The task to be run on a schedule.
        This function queries the database for records that need to be synced with Notion.
        If a record is new or updated, it is synced and its status is reset.

        Args:
        Session (SQLAlchemySession): The SQLAlchemy session factory.
        """
        logging.info("Sync to Notion task started")
        try:
            session = Session()
            rows = (
                session.query(ModelPlaceCard)
                .filter(
                    (ModelPlaceCard.is_new == True)
                    | (ModelPlaceCard.is_updated == True)
                )
                .all()
            )
            if rows:
                for row in rows:

                    response = self.update_or_insert_row(row.id_page, row.to_dict())
                    if isinstance(response, Dict):
                        row.is_new = False
                        row.is_updated = False
                        session.add(row)
                    else:
                        logging.info("update_or_insert_row failed")

            else:
                logging.info("No changes to sync to Notion")

            session.commit()
            session.close()
            logging.info("Sync to Notion task completed")
        except Exception as e:
            logging.error(f"Error in scheduled task from Notion: {e}")

    def get_full_url(self, short_url: str) -> str:
        """
        Expands a shortened Google Maps URL to its full URL.

        Args:
            short_url (str): The shortened URL to expand.

        Returns:
            str: The expanded URL.
        """
        response = requests.head(short_url, allow_redirects=True)
        return response.url

    def extract_coordinates_google_maps(self, url: str) -> tuple[float, float] | None:
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

    def get_coordinates_from_short_url(self, short_url: str) -> tuple[float, float]:
        """
        Expands a shortened Google Maps URL and extracts coordinates.

        Args:
            short_url (str): The shortened Google Maps URL.

        Returns:
            tuple[float, float]: A tuple containing the latitude and longitude.
        """
        full_url = self.get_full_url(short_url)
        return self.extract_coordinates_google_maps(full_url)

    def get_coordinates_from_link(self, url: str) -> Any | None:
        """
        Facade of extract, get coordinates and get full url.
        Returns tuple with coordinates.

        Args:
             url (str): short or full Google Maps link.
        """
        item_coordinates = None
        if url.startswith("https://"):
            if len(url) < 70:
                item_coordinates = self.get_coordinates_from_short_url(url)
            else:
                item_coordinates = self.extract_coordinates_google_maps(url)

        return item_coordinates

    def _scheduled_task_from_Notion(self, Session: SQLAlchemySession) -> None:
        """
        The task to be run on a schedule.
        This function queries the database for records that need to be synced with Notion.
        If a record is new or updated, it is synced and its status is reset.

        Args:
        Session (SQLAlchemySession): The SQLAlchemy session factory.

        This function performs the following steps:
        1. Reads all rows from Notion.
        2. Iterates over the rows in reverse order.
        3. For each row, it checks if a record with the same `id_page` and `is_updated=False` exists in the database.
        4. If such a record exists, it logs the details.
        5. If no such record exists or if an unchanged record is found, it creates a new `ModelPlaceCard` instance.
        6. Updates the `ModelPlaceCard` instance with data from the Notion row.
        7. Sets the `is_updated` field to `True`.
        8. Adds the `ModelPlaceCard` instance to the session.
        9. Commits the session after processing all rows.
        10. Handles any exceptions that occur during the process, logging the error and rolling back the session if necessary.
        """
        logging.info("Sync from Notion task started")
        from core.db_functions import search_by_key

        session = Session()
        try:
            rows = self.read_all_rows()
            for num in reversed(rows):
                model_place_card = (
                    session.query(ModelPlaceCard)
                    .filter_by(id_page=num["id"], is_updated=False)
                    .first()
                )
                no_change_place_card = (
                    session.query(ModelPlaceCard)
                    .filter_by(id_page=num["id"], is_updated=True)
                    .first()
                )

                if no_change_place_card:
                    logging.info(
                        f"no_change_place_card {no_change_place_card.Name} - {no_change_place_card.id_page}"
                    )
                else:
                    if not model_place_card:
                        model_place_card = ModelPlaceCard()
                        logging.info("model_place_card created")
                    for keys, values in num.items():

                        if keys == "id":
                            model_place_card.id_page = values
                        if keys == "properties":
                            for key, value in values.items():

                                if key == "Name":
                                    model_place_card.Name = search_by_key(
                                        value, "plain_text"
                                    )

                                if key == "Type":
                                    model_place_card.type = search_by_key(value, "name")

                                if key == "ID":
                                    model_place_card.ID = search_by_key(value, "number")

                                if key == "Photo Google Drive":
                                    model_place_card.photo = search_by_key(value, "url")

                                if key == "Location":
                                    if value["select"]:
                                        model_place_card.location = value["select"][
                                            "name"
                                        ]
                                    else:
                                        model_place_card.location = "Not specified"

                                if key == "Google Map":
                                    google_map_link = search_by_key(value, "url")
                                    if model_place_card.google_map != google_map_link:
                                        if google_map_link:
                                            model_place_card.google_map = (
                                                google_map_link
                                            )

                                        item_coordinates = (
                                            self.get_coordinates_from_link(
                                                model_place_card.google_map
                                            )
                                        )
                                        if item_coordinates:
                                            model_place_card.coordinates = str(
                                                item_coordinates
                                            )[1:-2]
                                            logging.info(
                                                f"Get coord to {model_place_card.Name}: {item_coordinates}"
                                            )
                                        else:
                                            model_place_card.google_map = (
                                                google_map_link
                                            )

                                if key == "Phone Number":
                                    model_place_card.phone_number = search_by_key(
                                        value, "plain_text"
                                    )

                                if key == "WhatsApp Number":
                                    model_place_card.whatsapp = search_by_key(
                                        value, "plain_text"
                                    )

                                if key == "Hours of Operation":
                                    model_place_card.hours_of_operation = search_by_key(
                                        value, "plain_text"
                                    )

                                if key == "Owner / Manager":
                                    model_place_card.manager_phone_number = (
                                        search_by_key(value, "plain_text")
                                    )
                        if (
                            not model_place_card.coordinates
                            and model_place_card.google_map
                        ):
                            item_coordinates = None
                            google_map_link = model_place_card.google_map
                            try:
                                item_coordinates = self.get_coordinates_from_link(
                                    google_map_link
                                )
                            except Exception as e:
                                logging.error(f"Error in item coordinates: {e}")

                            if item_coordinates:
                                model_place_card.coordinates = str(item_coordinates)[
                                    1:-2
                                ]
                                logging.info(
                                    f"Get coord to new place {model_place_card.Name}: {item_coordinates}"
                                )
                            else:
                                model_place_card.coordinates = "Bad url"

                        session.add(model_place_card)

            session.commit()
            logging.info("Sync from Notion task completed")
        except Exception as e:
            logging.error(f"Error in scheduled task to Notion: {e}")
            session.rollback()
        finally:
            session.close()
