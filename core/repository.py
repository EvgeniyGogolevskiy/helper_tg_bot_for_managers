from core.db import get_db
from core.model import ModelPlaceCard
from sqlalchemy import func, select
from models.place_card import PlaceCard
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Repository:
    """
    A class to manage DB.

    Attributes:
        logger (logging.Logger): Logger object for logging events.
    """

    def __init__(self, db=get_db) -> None:
        """
        Initializes.

        Args:
            get_db  function for accese to DB
        """
        self.conn = db()

    def read_card(self, name: str) -> ModelPlaceCard:
        """
        Reads card of place by id and returns it.

        Attributes:
            name (str): name of place

        Returns:
            ModelPlaceCard: The data from the DB.
        """
        correct_card = self.conn.execute(
            select(ModelPlaceCard).where(ModelPlaceCard.name == name)
        ).scalar()
        if correct_card:
            logger.info(f"Reading card id {name}")
            return correct_card
        else:
            logger.info(f"Card id {name} not found")
            raise KeyError("Card Not Found")

    def insert_card(self, data: ModelPlaceCard) -> None:
        """
        Insert card of place.

        Attributes:
        data (ModelPlaceCard): information about place.
        """
        self.conn.add(data)
        self.conn.commit()
        self.conn.refresh(data)
        logger.info(f"Insert card id {data.name}")

    def delete_card(self, name: str) -> None:
        """
        Delete card of place by id.

        Attributes:
            name (str): name of place
        """
        correct_card = self.conn.execute(
            select(ModelPlaceCard).where(ModelPlaceCard.name == name)
        ).scalar()
        if correct_card:
            self.conn.delete(correct_card)
            self.conn.commit()
            logger.info(f"Deleted card id {name}")
        else:
            logger.info(f"Card id {name} not found")
            raise KeyError("Card Not Found")

    def update_card(self, name: str, data: PlaceCard) -> None:
        """
        Update card of place by id.

        Attributes:
            name (str): name of place
        """
        correct_card = self.read_card(name=name)
        if correct_card:
            correct_card.name, correct_card.photo, correct_card.tp = (
                data.name,
                data.photos,
                data.type,
            )
            self.conn.commit()
            self.conn.refresh(correct_card)
            logger.info(f"Updated card id {name}")
        else:
            logger.info(f"Card id {name} not found")
            raise KeyError("Card Not Found")


repo = Repository()
