from bot.telegram_bot import TelegramBot
from config import TOKEN
from core.db import init_db
from config import NOTION_API_ID, NOTION_DATABASE_ID
from models.notion import Notion
import threading

if __name__ == "__main__":
    """
    Main entry point for executing the bot.

    Initializes and starts the TelegramBot instance with the provided token.
    Initializes sqlite
    """
    init_db()

    Notion_session = Notion(NOTION_API_ID, NOTION_DATABASE_ID)
    sync_thread = threading.Thread(target=Notion_session.sync)
    sync_thread.daemon = True
    sync_thread.start()

    bot = TelegramBot(TOKEN)
    bot.start_bot()
