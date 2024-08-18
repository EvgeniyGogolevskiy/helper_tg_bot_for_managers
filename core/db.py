from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
from config import mysql_db_path
from sqlalchemy.orm import Session
from config import NOTION_API_ID, NOTION_DATABASE_ID


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create engine DB
engine = create_engine(mysql_db_path)

# Create metadata
Base = declarative_base()

LocalSession = sessionmaker(autoflush=True, autocommit=False, bind=engine)


def get_db() -> Session:
    """Return a database session"""

    with LocalSession() as session:
        logger.info("Got session")
        return session


def init_db() -> None:
    """Initializes SQLite database"""
    import core.model

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    from core.db_functions import update_database_from_notion

    if not existing_tables:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            logger.info("Initialization DB")

            update_database_from_notion(NOTION_API_ID, NOTION_DATABASE_ID)
    else:
        logger.info("Database already initialized.")
