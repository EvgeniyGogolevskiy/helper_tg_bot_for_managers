import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import (
    Update,
    User,
    Message,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from bot.telegram_bot import TelegramBot
from config import TOKEN


@pytest.mark.asyncio
async def test_start():
    # Create a mock update object
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_chat = Chat(id=67890, type="private")
    mock_message = Message(
        message_id=1, date=None, chat=mock_chat, text="/start", from_user=mock_user
    )
    mock_update = Update(update_id=1001, message=mock_message)

    # Create a mock context object
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    # Mock the TelegramUser.auth method
    with patch(
        "models.telegram_user.TelegramUser.auth", return_value=MagicMock(role="admin")
    ) as mock_auth:
        bot = TelegramBot(token=TOKEN)

        # Call the start method
        await bot.start(mock_update, mock_context)

        # Check that the auth method was called with the correct user_id
        mock_auth.assert_called_once_with(12345)

        button_begin = InlineKeyboardButton(
            text="Show place card", callback_data="button_add_pressed"
        )

        show_unfilled_button = InlineKeyboardButton(
            text="Show unfilled places", callback_data="show_unfilled_places"
        )

        keyboard = InlineKeyboardMarkup([[button_begin], [show_unfilled_button]])

        mock_context.bot.send_message.assert_called_once_with(
            chat_id=67890, text="Hi! Choose an action:", reply_markup=keyboard
        )


@pytest.mark.asyncio
async def test_start_unauthorized():
    # Create a mock update object
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_chat = Chat(id=67890, type="private")
    mock_message = Message(
        message_id=1, date=None, chat=mock_chat, text="/start", from_user=mock_user
    )
    mock_update = Update(update_id=1001, message=mock_message)

    # Create a mock context object
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    # Mock the TelegramUser.auth method to return None (unauthorized user)
    with patch(
        "models.telegram_user.TelegramUser.auth", return_value=None
    ) as mock_auth:
        bot = TelegramBot(token=TOKEN)

        # Call the start method
        await bot.start(mock_update, mock_context)

        # Check that the auth method was called with the correct user_id
        mock_auth.assert_called_once_with(12345)

        # Check that send_message was called with the correct parameters
        mock_context.bot.send_message.assert_called_once_with(
            chat_id=67890, text="Your ID is not authorized"
        )
