import logging
from typing import Optional, Type, NoReturn
import pandas as pd
from sqlalchemy import create_engine
import os
from models.notion import Notion
from core.model import ModelPlaceCard
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import mysql_db_path
from logging.handlers import RotatingFileHandler

pd.set_option("display.max_colwidth", None)
pd.set_option("display.max_rows", None)

# log file path
log_file_path = os.path.abspath("update_database.log")

# log configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


class FlushFileHandler(logging.FileHandler):
    """
    Custom FileHandler that flushes after every log message.
    """

    def emit(self, record) -> None:
        super().emit(record)
        self.flush()


# delete standard FileHandler
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.FileHandler):
        logging.getLogger().removeHandler(handler)

# add custom FileHandler
logging.getLogger().addHandler(
    FlushFileHandler(log_file_path, mode="w", encoding="utf-8")
)

# Size settings
max_log_file_size = 1 * 1024 * 1024  # 1 MB
backup_count = 5  # Number of backup copies"
rotating_handler = RotatingFileHandler(
    log_file_path,
    mode="w",
    encoding="utf-8",
    maxBytes=max_log_file_size,
    backupCount=backup_count,
)


# Set FlushFileHandler, worк as  RotatingFileHandler
class FlushRotatingFileHandler(FlushFileHandler, RotatingFileHandler):
    pass


# add users RotatingFileHandler
logging.getLogger().addHandler(
    FlushRotatingFileHandler(
        log_file_path,
        mode="w",
        encoding="utf-8",
        maxBytes=max_log_file_size,
        backupCount=backup_count,
    )
)


def search_by_key(dictionary: dict, key: str) -> str:
    """
    Searches for all values associated with the specified key in a nested dictionary or list.

    Args:
    dictionary (dict): The nested dictionary or list in which to perform the search.
    key (str): The key whose values need to be found.

    Returns:
    str: A string containing all the found values, separated by commas.
    """
    results = []

    def recursive_search(d, target_key):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == target_key:
                    results.append(v)
                if isinstance(v, (dict, list)):
                    recursive_search(v, target_key)
        elif isinstance(d, list):
            for item in d:
                recursive_search(item, target_key)

    recursive_search(dictionary, key)
    return results[0] if results else None


def update_database_from_notion(API_ID: str, DATABASE_ID: str) -> None:
    """
    Update sqlite database from notion database with sqlalchemy
    """

    # db_path = "core/database.db"
    logging.info(f"Database path: {mysql_db_path}")

    # connect to database
    engine = create_engine(mysql_db_path)
    logging.info(f"Connecting to database at: {mysql_db_path}")

    Session = sessionmaker(bind=engine)
    session = Session()
    Notion_session = Notion(API_ID, DATABASE_ID)
    rows = Notion_session.read_all_rows()
    for num in reversed(rows):
        model_place_card = ModelPlaceCard()
        for keys, values in num.items():
            logging.info(f"Connecting to database at: {keys}:{values}")

            if keys == "id":
                model_place_card.id_page = values
            if keys == "properties":
                for key, value in values.items():

                    if key == "Name":
                        model_place_card.Name = search_by_key(value, "plain_text")

                    if key == "Type":
                        model_place_card.type = search_by_key(value, "name")

                    if key == "ID":
                        model_place_card.ID = search_by_key(value, "number")

                    if key == "Photo Google Drive":
                        model_place_card.photo = search_by_key(value, "url")

                    if key == "Google Map":
                        model_place_card.google_map = search_by_key(value, "url")

                    if key == "Phone Number":
                        model_place_card.phone_number = search_by_key(
                            value, "plain_text"
                        )

                    if key == "WhatsApp Number":
                        model_place_card.whatsapp = search_by_key(value, "plain_text")

                    if key == "Hours of Operation":
                        model_place_card.hours_of_operation = search_by_key(
                            value, "plain_text"
                        )

                    if key == "Owner / Manager":
                        model_place_card.manager_phone_number = search_by_key(
                            value, "plain_text"
                        )
                    if key == "Location":
                        model_place_card.location = search_by_key(value, "name")

        session.add(model_place_card)
    session.commit()


def find_company_by_name(name: str) -> Optional[ModelPlaceCard]:
    """
    Find a company by its name. If the company does not exist, create a new one.

    Args:
    name (str): The name of the company to find or create.

    Returns:
    Optional[ModelPlaceCard]: The found or newly created ModelPlaceCard instance.
    """
    engine = create_engine(mysql_db_path)
    logging.info(f"Connecting to database at: {mysql_db_path}")

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        company = session.query(ModelPlaceCard).filter_by(Name=name).first()
        if not company:
            company = ModelPlaceCard(Name=name)
            session.add(company)
            session.commit()
            session.refresh(company)
        return company
    finally:
        session.close()


def get_place_by_id(id: int) -> Optional[ModelPlaceCard]:
    """
    Find a company by its ID.

    Args:
    id (int): The ID of the company to find.

    Returns:
    Optional[ModelPlaceCard]: The found ModelPlaceCard instance.
    """
    engine = create_engine(mysql_db_path)
    logging.info(f"Connecting to database at: {mysql_db_path}")

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        company = session.query(ModelPlaceCard).filter_by(ID=id).first()
        return company
    finally:
        session.close()


def get_maps_filtered_rows() -> list[Type[ModelPlaceCard]]:
    """
    Returns list with all rows where column Google Map not blanked.

    Returns:
    list[Type[ModelPlaceCard]]: list with filtered rows.
    """
    engine = create_engine(mysql_db_path)
    logging.info(f"Connecting to database in get filtered at: {mysql_db_path}")

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        filtered = (
            session.query(ModelPlaceCard).filter(ModelPlaceCard.google_map != "").all()
        )
        return filtered
    finally:
        session.close()


def put_coordinates(model: ModelPlaceCard, location: tuple[float, float]) -> NoReturn:
    """
    Insert model with coordinates to database.

    Args:
    model (ModelPLaceCard): The instance of ModelPlaceCard object.
    location (tuple[float, float]): place coordinates
    """
    location = str(location)
    engine = create_engine(mysql_db_path)
    logging.info(f"Connecting to database in put coords at: {mysql_db_path}")

    Session = sessionmaker(bind=engine)
    session = Session()

    model.coordinates = location[1:-2]

    try:
        session.add(model)
        session.commit()
        logging.info(f"Fetch coordinates in database: {location}")
    finally:
        session.close()
