from config import id_list


class TelegramUser:
    """
    Represents a user in the Telegram system with a unique user ID and a role.

    Attributes:
        user_id (int): Unique identifier for the user.
        role (str): Role assigned to the user, defaulting to "Data Manager".
    """

    def __init__(self, user_id: int, role: str = "Data Manager") -> None:
        """
        Initializes the TelegramUser instance with a user ID and an optional role.

        Args:
            user_id (int): Unique identifier for the user.
            role (str, optional): Role assigned to the user. Defaults to "Data Manager".
        """
        self.user_id = user_id
        self.role = role

    @classmethod
    def auth(cls, user_id: int) -> "TelegramUser":
        """
        Authenticates a user by checking if their user ID exists in the id_list from config.py.

        Args:
            user_id (int): User ID to authenticate.

        Returns:
            TelegramUser: An authenticated TelegramUser instance if found, None otherwise.
        """
        for user in id_list:
            if user == user_id:
                return cls(user_id=user_id)
        return None
