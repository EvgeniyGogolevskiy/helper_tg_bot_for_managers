
# Telegram Bot for Adding Organizations in Costa Rica

This project is a Telegram bot designed to simplify the process of adding new organizations for managers of a company. The bot provides a streamlined interface that allows managers to effortlessly input organization details. The bot integrates with a Notion database to manage and store organization data, ensuring a smooth and efficient workflow.

## Features

- **User-Friendly Interface:** Easily add new organizations through a simple chat with the bot.
- **Notion Database Integration:** Directly interacts with a Notion database to store and manage organization data.
- **Access Control:** Only authorized Telegram accounts can interact with the bot.
- **Notifications:** Sends updates to specified Telegram accounts when new organizations are added.

## Getting Started

### Prerequisites

Before you can run the bot, make sure you have the following installed:

- Python 3.8 or higher
- `pip` (Python package manager)

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```

2. **Create a `config.py` file:**

   Inside the project directory, create a file named `config.py` and add the necessary configuration details:

   ```python
   # config.py

   TOKEN = 'your-telegram-bot-token'  # Your Telegram bot's API token
   id_list = ['user_id_1', 'user_id_2']  # List of Telegram user IDs that can interact with the bot
   id_notification_list = ['user_id_3', 'user_id_4']   # List of Telegram user IDs that will receive notifications
   NOTION_API_ID = 'your-notion-api-id'  # api to your Notion
   NOTION_DATABASE_ID = 'your-notion-database-id'  # id to your notion database
   mysql_db_path = 'your-database-url'  # URL to your main database (if applicable)
   ```

3. **Install the required dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the bot:**

   ```bash
   python run.py
   ```

### Usage

After starting the bot, authorized users can add new organizations by interacting with the bot in Telegram. The bot will store all relevant data in the linked Notion database and send notifications to specified users.

## Configuration

Make sure to update the following settings in the `config.py` file:

- `TOKEN`: The API token for your Telegram bot.
- `id_list`: A list of Telegram user IDs allowed to interact with the bot.
- `id_notification_list`: A list of Telegram user IDs that will receive notifications when new organizations are added.
- `NOTION_API_ID` API to your Notion
- `NOTION_DATABASE_ID` id to your notion database
- `mysql_db_path` URL to your main database (if applicable)

## Deployment

To deploy the bot to a server or cloud platform, follow these steps:

1. **Set up a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   Ensure that the necessary environment variables, such as `TELEGRAM_TOKEN`, are set.

4. **Run the bot:**

   ```bash
   python run.py
   ```
