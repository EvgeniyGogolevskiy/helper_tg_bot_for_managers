import pytest
from models.telegram_user import TelegramUser
from config import id_list


@pytest.fixture
def user_setup():
    """Set up testing environment."""
    return {
        "user_id": id_list[1],  # Assuming the first id in the list is valid
        "invalid_user_id": 999999999,  # Assuming this id is invalid
        "role": "Data Manager",
        "telegram_user": TelegramUser(id_list[1], "Data Manager"),
    }


def test_telegram_user_init(user_setup):
    """Test __init__ method of TelegramUser class."""
    assert user_setup["telegram_user"].user_id == user_setup["user_id"]
    assert user_setup["telegram_user"].role == user_setup["role"]


def test_telegram_user_auth_valid_user(user_setup):
    """Test auth method of TelegramUser class with valid user."""
    user = TelegramUser.auth(user_setup["user_id"])
    assert isinstance(user, TelegramUser)
    assert user.user_id == user_setup["user_id"]


def test_telegram_user_auth_invalid_user(user_setup):
    """Test auth method of TelegramUser class with invalid user."""
    user = TelegramUser.auth(user_setup["invalid_user_id"])
    assert user is None
