import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.model import ModelPlaceCard


@pytest.fixture
def sample_data() -> dict[str, str | dict | list]:
    """
    A fixture that provides a sample of data for testing.
    """

    return {
        "key1": "value1",
        "key2": {"nested_key": "nested_value"},
        "key3": [{"inner_key": "inner_value"}],
    }


@pytest.fixture
def db_session() -> Session:
    """
    A fixture that creates and provides a database session for testing.
    """

    engine = create_engine("sqlite:///:memory:")
    ModelPlaceCard.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)
    session = test_session()
    yield session
    session.close()


@pytest.fixture
def mock_notion() -> type:
    """
    A fixture that provides a mock object for the Notion API.
    """

    class MockNotion:
        def __init__(self, *args):
            pass

        def read_all_rows(self):
            return [
                {
                    "id": "test_id",
                    "properties": {
                        "Name": {"plain_text": "Test Company"},
                        "Type": {"name": "Test Type"},
                        "ID": {"number": 1},
                        "Photo Google Drive": {"url": "http://test.com/photo"},
                        "Google Map": {"url": "http://test.com/map"},
                        "Phone Number": {"plain_text": "123456789"},
                        "WhatsApp Number": {"plain_text": "987654321"},
                        "Hours of Operation": {"plain_text": "9-5"},
                        "Owner / Manager": {"plain_text": "John Doe"},
                    },
                }
            ]

    return MockNotion
