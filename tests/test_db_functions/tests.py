import pytest
from sqlalchemy.orm import Session

from config import NOTION_API_ID, NOTION_DATABASE_ID
from core.db_functions import (
    find_company_by_name,
    search_by_key,
    update_database_from_notion,
)
from core.model import ModelPlaceCard


class TestSearchByKey:
    """
    Testing the search_by_key function
    """

    def test_search_by_key_dict(
        self, sample_data: dict[str, str | dict | list]
    ) -> None:
        """
        Searching in the dictionary
        """

        assert search_by_key(sample_data, "key1") == "value1"
        assert search_by_key(sample_data, "nested_key") == "nested_value"

    def test_search_by_key_list(self, sample_data: dict[str, str | dict | list]):
        """
        Searching in a list of dictionaries
        """

        assert search_by_key(sample_data, "inner_key") == "inner_value"

    def test_search_by_key_non_existing_key(
        self, sample_data: dict[str, str | dict | list]
    ):
        """
        Searching for a non-existent key
        """

        assert search_by_key(sample_data, "non_existing_key") is None


class TestUpdateDatabaseFromNotion:
    """
    Testing the update_database_from_notion function
    """

    def test_update_database_from_notion(
        self, db_session: Session, mock_notion: type, monkeypatch
    ):
        # Substitution of dependencies
        monkeypatch.setattr("core.db_functions.Notion", mock_notion)
        monkeypatch.setattr(
            "core.db_functions.create_engine", lambda x: db_session.bind
        )
        monkeypatch.setattr(
            "core.db_functions.sessionmaker", lambda bind: lambda: db_session
        )

        update_database_from_notion(NOTION_API_ID, NOTION_DATABASE_ID)

        company = db_session.query(ModelPlaceCard).first()
        assert company is not None
        assert company.Name == "Test Company"
        assert company.type == "Test Type"
        assert company.ID == "1"
        assert company.photo == "http://test.com/photo"
        assert company.google_map == "http://test.com/map"
        assert company.phone_number == "123456789"
        assert company.whatsapp == "987654321"
        assert company.hours_of_operation == "9-5"
        assert company.manager_phone_number == "John Doe"


class TestFindCompanyByName:
    """
    Testing the find_company_by_name function
    """

    @pytest.mark.parametrize(
        "company_name",
        [
            "Existing Company",
            "New Company",
        ],
    )
    def test_find_company_by_name(
        self, db_session: Session, company_name: str, monkeypatch
    ):
        # Data preparation
        if company_name == "Existing Company":
            existing_company = ModelPlaceCard(Name="Existing Company")
            db_session.add(existing_company)
            db_session.commit()

        # Substitution of dependencies
        monkeypatch.setattr(
            "core.db_functions.create_engine", lambda x: db_session.bind
        )
        monkeypatch.setattr(
            "core.db_functions.sessionmaker", lambda bind: lambda: db_session
        )

        result = find_company_by_name(company_name)

        assert result is not None
        assert result.Name == company_name
        assert (
            db_session.query(ModelPlaceCard).filter_by(Name=company_name).count() == 1
        )
