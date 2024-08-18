import logging
import re
import telegram.error
from sqlalchemy.orm.exc import DetachedInstanceError
from typing import NoReturn
from telegram import (
    KeyboardButton,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ForceReply,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

from sqlalchemy.orm import sessionmaker
from models.google_services import GoogleDrive, GoogleMap
from models.telegram_user import TelegramUser
from models.notification import NotificationSender
from core.db_functions import find_company_by_name, get_place_by_id
from core.db import engine, get_db
from core.model import ModelPlaceCard

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """
    A class to handle Telegram bot interactions and manage data operations.

    Attributes:
        token (str): The bot token for authentication with the Telegram API.
        current_card_id (dict, optional): The current card ID being managed. Defaults to None.
        field_to_update (str, optional): The field to update. Defaults to None.
        application (Application): The application instance for handling Telegram updates.
    """

    def __init__(self, token: str) -> None:
        """
        Initializes the TelegramBot instance with the provided bot token.

        Args:
            token (str): The bot token for authentication with the Telegram API.
        """
        logger.info("Initializing TelegramBot instance")
        self.token = token
        self.current_card_id = None
        self.field_to_update = None
        self.application = ApplicationBuilder().token(token).build()

    def validate_name(self, name: str) -> bool:
        """
        Validates the company name.

        Args:
            name (str): The company name to validate.

        Returns:
            bool: True if the name is valid, False otherwise.
        """
        return bool(re.match(r"^[a-zA-Z0-9\s.,:;!?'-]+$", name))

    def validate_type(self, type: str) -> bool:
        """
        Validates the company type.

        Args:
            type (str): The company type to validate.

        Returns:
            bool: True if the type is valid, False otherwise.
        """
        valid_types = ["Places to eat", "Adventures", "Services"]
        return type in valid_types

    def validate_photos(self, photos: list) -> bool:
        """
        Validates the company photos.

        Args:
            photos (list[PhotoSize]): The list of photos to validate.

        Returns:
            bool: True if the photos are valid, False otherwise.
        """
        return isinstance(photos, list) and all(
            hasattr(photo, "file_id") for photo in photos
        )

    def validate_google_maps(self, url: str) -> bool:
        """
        Validates the Google Maps URL.

        Args:
            url (str): The Google Maps URL to validate.

        Returns:
            bool: True if the URL is valid, False otherwise.
        """
        return bool(re.match(r"^https:\/\/maps\.app\.goo\.gl\/[a-zA-Z0-9]+$", url))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handles the start command to authenticate the user and provide options for adding a new organization.

        Args:
            update (Update): The update object containing the incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        logger.info("Handling start command")
        user_id = update.message.from_user.id
        user = TelegramUser.auth(user_id)

        if user:
            logger.info(f"Authenticated user ID: {user_id}, Role: {user.role}")

            button_begin = InlineKeyboardButton(
                text="Show place card", callback_data="button_add_pressed"
            )

            show_unfilled_button = InlineKeyboardButton(
                text="Show unfilled places", callback_data="show_unfilled_places"
            )

            keyboard = InlineKeyboardMarkup([[button_begin], [show_unfilled_button]])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Hi! Choose an action:",
                reply_markup=keyboard,
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text="Your ID is not authorized"
            )
            logger.warning(f"Unauthorized ID: {user_id}")

    async def button_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handles button presses to add a new organization or update existing ones.

        Args:
            update (Update): The update object containing the incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        logger.info("Handling button press")
        query = update.callback_query

        await query.answer()  # unlock the button

        if query.data == "button_add_pressed":
            logger.info(f"Processed {query.data} from user {query.from_user.id}")
            await self.add_company(context, update)

    async def show_unfilled_places(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Displays a message prompting the user to select a location.

        This method sends a message asking the user to select a location when the "Show unfilled places" button is pressed.

        Args:
            update (Update): The update object containing the incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        logger.info("Showing unfilled places")

        # Define the keyboard with a button to request location and an Exit button
        location_button = KeyboardButton(
            text="Share your location", request_location=True
        )
        keyboard = [[location_button], ["Exit"]]

        # Create the ReplyKeyboardMarkup
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        # Send the message with the custom keyboard
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please share your location to find unfilled places near you:",
            reply_markup=reply_markup,
        )

    async def add_company(
        self, context: ContextTypes.DEFAULT_TYPE, update: Update
    ) -> None:
        """
        Handles the addition of a new company to the database.

        Args:
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
            update (Update): The update object containing the incoming update.
        """
        logger.info("Adding company")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please enter the name of the company you want to know about.",
            reply_markup=ForceReply(selective=True),
        )

    def dict_to_place_card(self, data: dict) -> ModelPlaceCard:
        return ModelPlaceCard(
            Name=data.get("Name", ""),
            ID=data.get("ID", ""),
            type=data.get("type", ""),
            photo=data.get("photo", ""),
            location=data.get("location", ""),
            google_map=data.get("google_map", ""),
            phone_number=data.get("phone_number", ""),
            whatsapp=data.get("whatsapp", ""),
            manager_phone_number=data.get("manager_phone_number", ""),
            hours_of_operation=data.get("hours_of_operation", ""),
        )

    async def handle_company_name(
        self, update: Update, context: CallbackContext
    ) -> None:
        """
        Handles the input of a company name and retrieves or creates a new card.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Handling company name")
        company_name = update.message.text
        logging.info(f"Company name received: {company_name}")

        # Validate company name
        if not self.validate_name(company_name):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid name. Please enter a valid name with only letters, spaces, numbers and punctuation marks.",
                reply_markup=ForceReply(selective=True),
            )
            # Request the user to re-enter the company name
            await self.add_company(context, update)
            return  # Exit the function to wait for another input

        with get_db() as session:
            companies = session.query(ModelPlaceCard).filter_by(Name=company_name).all()

        if companies and len(companies) > 1:
            keyboard = []
            for company in companies:
                callback_data = f"select_company_{company.ID}"
                company_location = company.location or "Not specified"
                company_type = company.type or "Not specified"
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"{company.Name} (Location: {company_location}, Type: {company_type})",
                            callback_data=callback_data,
                        )
                    ]
                )
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = "Multiple companies found with the same name. Please select one:"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                reply_markup=reply_markup,
            )
            logger.info("Multiple companies found")
        else:
            if companies:
                company = companies[0]
                context.user_data["current_card"] = companies[0]
                message = "Company found."
            else:
                with get_db() as session:
                    company = ModelPlaceCard(Name=company_name)
                    session.add(company)
                    session.commit()
                    session.refresh(company)
                context.user_data["current_card"] = company
                message = "Company not found. A new one was created."
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=message
            )
            await self._show_place(update=update, context=context, company=company)

    async def select_company(self, update: Update, context: CallbackContext) -> None:
        """
        Handles getting places with the same name.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """

        try:
            query = update.callback_query
            await query.answer()

            logger.info(f"Callback data: {query.data}")
            company_id = int(query.data.split("_")[-1])
            logger.info(f"Extracted company ID: {company_id}")

            with get_db() as session:
                company = session.query(ModelPlaceCard).filter_by(ID=company_id).first()

            if company:
                context.user_data["current_card"] = company

                # Delete message with selection buttons
                await query.delete_message()

                await self._show_place(update=update, context=context, company=company)
            else:
                await query.edit_message_text(text="Error: Company not found.")

        except Exception as e:
            logger.error(f"Error in select_company: {e}", exc_info=True)
            await update.effective_chat.send_message(
                "An error occurred while processing your selection."
            )

    async def _show_place(
        self, context: CallbackContext, update: Update, company: ModelPlaceCard
    ) -> None:
        await self.show_place_card(update=update, context=context, company=company)
        await self.show_editbar(update=update, context=context)
        await self.show_edit_keyboard(update=update, context=context)

    async def show_place_card(
        self,
        update: Update,
        context: CallbackContext,
        company: ModelPlaceCard,
        edit_state: bool = False,
    ) -> None:
        """
        Handles displaying the details of a place card.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
            company (ModelPlaceCard): instance of model.ModelPlaceCard object from database.
            edit_state (bool): flag of state when user listing places and decide to edit place card,
             while loc_conv_handler.
        """
        logger.info("Displaying place card details")

        # Format the information message with all details
        info_message = (
            f"Name: {company.Name}\n"
            f"Type: {company.type}\n"
            f"Photos: {company.photo}\n"
            f"Google map: {company.google_map}\n"
            f"Phone numbers: {company.phone_number}\n"
            f"WhatsApp: {company.whatsapp}\n"
            f"Manager Phone Number: {company.manager_phone_number}\n"
            f"Hours of operation: {company.hours_of_operation}\n"
        )

        if edit_state:
            keyboard = [[InlineKeyboardButton("Edit", callback_data="edit_place_card")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=info_message,
                reply_markup=reply_markup,
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=info_message
        )

    async def show_editbar(self, update: Update, context: CallbackContext) -> None:
        """
        Handles displaying an edit bar for the user to select a field to update.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Displaying edit bar")
        keyboard_layout = [
            [InlineKeyboardButton("Name", callback_data="Name")],
            [InlineKeyboardButton("Type", callback_data="type")],
            [InlineKeyboardButton("Photos", callback_data="photo")],
            [InlineKeyboardButton("Google map", callback_data="google_map")],
            [InlineKeyboardButton("Phone numbers", callback_data="phone_number")],
            [InlineKeyboardButton("WhatsApp Number", callback_data="whatsapp")],
            [
                InlineKeyboardButton(
                    "Manager Phone Number", callback_data="manager_phone_number"
                )
            ],
            [
                InlineKeyboardButton(
                    "Hours of operation", callback_data="hours_of_operation"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard_layout)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Choose a field to edit:",
            reply_markup=reply_markup,
        )

    async def show_edit_keyboard(
        self, update: Update, context: CallbackContext
    ) -> None:
        """
        Handles displaying a keyboard for the user to confirm or cancel changes.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Displaying edit keyboard")
        keyboard = [["Exit", "Save"]]

        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        if update.message:
            await update.message.reply_text(
                "Save when you are finished, or exit to cancel changes",
                reply_markup=reply_markup,
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Save when you are finished, or exit to cancel changes",
                reply_markup=reply_markup,
            )

    async def handle_exit(self, update: Update, context: CallbackContext):
        """
        Handles the exit command to return to the main menu.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Exiting to the main menu")

        context.user_data.clear()
        await update.message.reply_text("You have returned to the main menu")
        await self.start(update=update, context=context)
        return ConversationHandler.END

    async def drive_upload(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> NoReturn:
        current_card: ModelPlaceCard = context.user_data["current_card"]
        user = update.message.from_user.first_name

        try:
            drive = GoogleDrive()
            folder_link = drive.upload_photo(
                folder_name=current_card.Name,
                links=context.user_data["photos_received"],
            )
            current_card.photo = f"{folder_link}"
            context.user_data.pop("photos_received")
            logger.info(f"Photos from {user} successfully uploaded")
        except Exception as ex:
            logging.error(f"Error while GoogleDrive uploading: {ex}")
            current_card.photo = "None"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Error while uploading photos, try again",
            )

    async def handle_save(self, update: Update, context: CallbackContext) -> None:
        """
        Handles the '/save' command issued by a user. This command updates a specified field in the database,
        sends notifications about the update, and shows the updated place card to the user.

        This method logs the saving action, sends a reply to the user confirming that the place card has been saved,
        and invokes the display of this place card. It also handles the writing of updated data to Google Sheets and
        manages notifications related to data changes. If data retrieval from Google Sheets is successful, it sends
        a notification; otherwise, it logs the absence of returned data.

        Args:
            update (Update): The update object containing the incoming Telegram update.
            context (CallbackContext): The context from the update, used here for managing asynchronous tasks and data.

        Raises:
            Exception: Logs any exceptions that occur during notification sending or other asynchronous operations.
        """
        logger.info("Saving place card")
        logger.info(f"user ID {update.message.from_user.id}")

        place_card_data = context.user_data.get("current_card")

        if isinstance(place_card_data, dict):
            place_card_data = self.dict_to_place_card(data=place_card_data)
            context.user_data["current_card"] = place_card_data

        if not isinstance(place_card_data, ModelPlaceCard):
            logger.error("place_card_data is not an instance of ModelPlaceCard")
            await update.message.reply_text("There was an error processing your data.")
            return

        drive_upload_flag = context.user_data.get("photos_received")
        if drive_upload_flag:
            await self.drive_upload(update=update, context=context)

        old_place_card = None
        with get_db() as session:
            old_place_card = (
                session.query(ModelPlaceCard).filter_by(ID=place_card_data.ID).first()
            )
            if old_place_card:
                old_place_card_dict = old_place_card.__dict__.copy()
                old_place_card_dict.pop(
                    "_sa_instance_state", None
                )  # Removing SQLAlchemy Service Attribute

            existing_place_cards = (
                session.query(ModelPlaceCard).filter_by(ID=place_card_data.ID).all()
            )

            if existing_place_cards:
                for place_card in existing_place_cards:
                    place_card.Name = place_card_data.Name
                    place_card.type = place_card_data.type
                    place_card.photo = place_card_data.photo
                    place_card.location = place_card_data.location
                    place_card.google_map = place_card_data.google_map
                    place_card.phone_number = place_card_data.phone_number
                    place_card.whatsapp = place_card_data.whatsapp
                    place_card.manager_phone_number = (
                        place_card_data.manager_phone_number
                    )
                    place_card.hours_of_operation = place_card_data.hours_of_operation
                    place_card.is_updated = True
            else:
                session.add(place_card_data)

            session.commit()

        await update.message.reply_text("You saved the place card")

        # Sending a change notification
        new_place_card = place_card_data.__dict__.copy()
        new_place_card.pop(
            "_sa_instance_state", None
        )  # Removing SQLAlchemy Service Attribute
        notification_sender = NotificationSender(token=self.token)
        await notification_sender.send_notification(
            payload=new_place_card,
            old_payload=old_place_card_dict,
            manager_id=update.message.from_user,
        )

        await self.show_place_card(
            update=update, context=context, company=place_card_data
        )
        context.user_data.clear()
        await self.start(update=update, context=context)
        return ConversationHandler.END

    async def handle_new_value(self, update: Update, context: CallbackContext) -> None:
        """
        Handles the input of a new value for the selected field.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Handling new value input")
        new_value = update.message.text

        # Check if the command is to show information
        if new_value.lower() == "show information":
            await self.show_place_card(
                update, context, company=context.user_data["current_card"]
            )
        else:
            # Try to update the value in the current card
            try:
                current_card = context.user_data["current_card"]

                # Check if the field to update exists in the current card
                if hasattr(current_card, context.user_data["field_to_update"]):
                    field_to_update = context.user_data["field_to_update"]

                    # Perform validation based on the field to update
                    if field_to_update == "Name" and not self.validate_name(new_value):
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="Invalid name. Please enter a valid name with only letters, spaces, and apostrophes.",
                        )
                        return
                    elif field_to_update == "type":
                        if new_value not in ["Places to eat", "Adventures", "Services"]:
                            keyboard_layout = [
                                [
                                    InlineKeyboardButton(
                                        "Places to eat", callback_data="Places to eat"
                                    )
                                ],
                                [
                                    InlineKeyboardButton(
                                        "Adventures", callback_data="Adventures"
                                    )
                                ],
                                [
                                    InlineKeyboardButton(
                                        "Services", callback_data="Services"
                                    )
                                ],
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard_layout)
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text="Invalid type. Please choose one of the following types:",
                                reply_markup=reply_markup,
                            )
                            return
                    elif field_to_update == "photo":
                        # Photos are handled separately in another method
                        if not update.message.photo or not self.validate_photos(
                            update.message.photo
                        ):
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text="Invalid photos. Please send valid photo files.",
                            )
                            return
                        new_value = (
                            update.message.photo
                        )  # Update with the actual photo list
                    elif (
                        field_to_update == "google_map"
                        and not self.validate_google_maps(new_value)
                    ):
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="Invalid input for google_map. Provide a link to Google Maps using the following format https://maps.app.goo.gl/{LocationID}.",
                        )
                        return
                    elif field_to_update in [
                        "phone_number",
                        "whatsapp",
                        "manager_phone_number",
                    ]:
                        # Validate and process phone number
                        digits_only = "".join(filter(str.isdigit, new_value))
                        if len(digits_only) == 8:
                            processed_number = "+506" + digits_only
                        elif len(digits_only) == 11 and digits_only.startswith("506"):
                            processed_number = "+" + digits_only
                        else:
                            processed_number = digits_only
                        new_value = processed_number

                    # Update the value in the current card
                    setattr(current_card, field_to_update, new_value)

                    # Also update the value in the context user_data
                    context.user_data["current_card"] = current_card
                    logger.info("Field updated successfully")

                    # Reset the update field
                    context.user_data.pop("field_to_update")

                    # Display updated information
                    await self.show_place_card(
                        update=update, context=context, company=current_card
                    )
                    await self.show_editbar(update=update, context=context)
                else:
                    logger.warning(
                        f"Invalid field: {context.user_data['field_to_update']}"
                    )
                    # Inform the user if the field is invalid
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Invalid field: {context.user_data['field_to_update']}",
                    )
            except Exception as e:
                # Handle any exceptions that occur during the update process
                logger.error(f"Error updating field: {str(e)}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=f"Error: {str(e)}"
                )

    async def button(self, update: Update, context: CallbackContext) -> NoReturn:
        """
        Handles button presses to select a field to update or type selection.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        data = update.callback_query.data
        current_card = context.user_data["current_card"]

        if isinstance(current_card, dict):
            current_card = self.dict_to_place_card(current_card)
            context.user_data["current_card"] = current_card

        # Check if the data corresponds to one of the field options
        if data in ["Places to eat", "Adventures", "Services"]:
            # Save the selected type to the current card
            current_card.type = data
            context.user_data.pop("field_to_update", None)

            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=f"Type updated to {data}"
                )

                await self.show_place_card(
                    update=update, context=context, company=current_card
                )
                await self.show_editbar(update=update, context=context)
            except DetachedInstanceError as e:
                logger.error(f"Error updating type: {str(e)}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=f"Error: {str(e)}"
                )
        else:
            # Handle selection of a field to update
            context.user_data["field_to_update"] = data
            if data == "type":
                # Display type options for selection
                keyboard_layout = [
                    [
                        InlineKeyboardButton(
                            "Places to eat", callback_data="Places to eat"
                        )
                    ],
                    [InlineKeyboardButton("Adventures", callback_data="Adventures")],
                    [InlineKeyboardButton("Services", callback_data="Services")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard_layout)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Choose a type:",
                    reply_markup=reply_markup,
                )
            else:
                await update.callback_query.answer()
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Enter new value for {data}",
                )

    async def add_photo(self, update: Update, context: CallbackContext) -> int:
        """
        Handles button presses to select a photo field to update.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Send photos below and then do /finish",
        )
        return 1

    async def photo_handler(self, update: Update, context: CallbackContext) -> int:
        """
        Handle updates with a photo when photo conversation handler running.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """

        user = update.message.from_user.first_name

        photo_file = await update.message.photo[-1].get_file()
        if photo_file.file_size <= 25000000:
            context.user_data.setdefault("photos_received", []).append(
                photo_file.file_path
            )
            logger.info(f"{user} added photo {photo_file.file_id}")
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Photo size should be < 25 megabytes",
            )

        return 1

    async def finish_photo(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> ConversationHandler.END:
        """
        Handle command /finish then start uploading photos from user_data['photos_received']
        by GoogleDrive.upload_photo() and rounding out conversation handler.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        amount_photo = len(context.user_data["photos_received"])
        current_card = context.user_data["current_card"]
        place_card_text = (
            f"{amount_photo} photo(s) will be uploaded when you press Save"
        )

        current_card.photo = place_card_text
        await self.show_place_card(update=update, context=context, company=current_card)
        await self.show_editbar(update=update, context=context)

        return ConversationHandler.END

    async def handle_location(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handles the location message sent by the user.

        Args:
            update (Update): The update object containing the incoming message.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """

        user_location = update.message.location
        latitude = user_location.latitude
        longitude = user_location.longitude

        logger.info(f"Received location: latitude={latitude}, longitude={longitude}")

        context.user_data.setdefault("location", [longitude, latitude])
        context.user_data.setdefault("page", 0)

        keyboard = [
            InlineKeyboardButton(text="With photos", callback_data="photo_true"),
            InlineKeyboardButton(text="Without photos", callback_data="photo_false"),
        ]
        reply_markup = InlineKeyboardMarkup([keyboard])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Choose places with(out) photo:",
            reply_markup=reply_markup,
        )
        return 1

    async def photo_callback(self, update: Update, context: CallbackContext) -> int:
        """
        Processes the value of the photo parameter.

        Args:
            update (Update): The update object containing the incoming message.
            context (CallbackContext): The context from the update.
        """
        text = ""
        query = update.callback_query
        await query.answer()

        if query.data == "photo_true":
            context.user_data.setdefault("photo_status", "True")
        elif query.data == "photo_false":
            context.user_data.setdefault("photo_status", "False")
            text = "out"

        text = (
            f"Send me radius(example: 0.5). Returns places around in 500m with{text} photos."
            f"If something went wrong send command /cancel_location"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
        )
        return 2

    async def send_venue_list(
        self, update: Update, context: CallbackContext, radius: float
    ) -> NoReturn:
        """
        Handling and processing venue list by radius and pagination.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
            radius (float): User radius value.
        """

        LEN_LIST = 3
        page = int(context.user_data["page"])
        start_id = page * LEN_LIST
        end_id = start_id + LEN_LIST
        max_page = 0

        places_list = context.user_data["places_list"]

        if places_list:
            if len(places_list) >= LEN_LIST:
                max_page = (len(places_list) / LEN_LIST) - 1
            elif max_page > 0:
                if max_page % int(max_page) > 0:
                    max_page = int(max_page) + 1
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="No places around in selected radius, use /cancel_location",
            )
            return

        context.user_data.setdefault("max_page", max_page)

        keyboard = []
        if page < max_page:
            for item in places_list[start_id:end_id]:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            item["message"], callback_data=f'notion_{item["id"]}'
                        )
                    ]
                )
        elif page == max_page:
            end_id = len(places_list)
            for item in places_list[start_id:end_id]:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            item["message"], callback_data=f'notion_{item["id"]}'
                        )
                    ]
                )

        buttons = [
            InlineKeyboardButton(text="<", callback_data="page_prev"),
            InlineKeyboardButton(text=">", callback_data="page_next"),
        ]

        if len(places_list) <= LEN_LIST:
            keyboard.append(
                [InlineKeyboardButton(text="Exit", callback_data="exit_location")]
            )
            reply_markup = InlineKeyboardMarkup(keyboard)
        elif len(places_list) > LEN_LIST and page <= max_page:
            keyboard.append(buttons)
            keyboard.append(
                [InlineKeyboardButton(text="Exit", callback_data="exit_location")]
            )
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = None

        if radius <= 1:
            radius = round(radius, 3)
            distance = f"{radius * 1000} m"
        else:
            radius = round(radius, 2)
            distance = f"{radius} km"

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    f"Places in radius {distance}:", reply_markup=reply_markup
                )
            except telegram.error.BadRequest as ex:
                logging.debug(f"{ex}")
        else:
            await update.message.reply_text(
                text=f"Places in radius {distance}:", reply_markup=reply_markup
            )

    async def take_radius(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handles the radius in text message sent by the user.

        Args:
            update (Update): The update object containing the incoming message.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        if update.message.text == "/cancel_location":
            context.user_data.clear()
            await self.cancel_location(update, context)
            return ConversationHandler.END

        user_radius = float(update.message.text)
        context.user_data.setdefault("radius", user_radius)
        longitude, latitude = context.user_data.get("location")

        maps = GoogleMap()
        places_list = maps.radius_list(
            longitude=longitude,
            latitude=latitude,
            radius=context.user_data["radius"],
            photo=context.user_data["photo_status"],
        )

        context.user_data.setdefault("places_list", places_list)

        await self.send_venue_list(update=update, context=context, radius=user_radius)
        return 3

    async def prev_next_button(self, update: Update, context: CallbackContext) -> int:
        """
        Handles page_prev|page_next|notion_ callback data.

        Args:
            update (Update): The update object containing the incoming message.
            context (CallbackContext): The context from the update.
        """

        query = update.callback_query
        await query.answer()

        current_page = context.user_data["page"]

        if query.data.startswith("page_"):
            pos = query.data.split("_")[1]
            if pos == "next":
                user_max_page = context.user_data["max_page"]
                if current_page < user_max_page:
                    context.user_data.update({"page": current_page + 1})
            elif pos == "prev":
                if current_page > 0:
                    context.user_data.update({"page": current_page - 1})
                else:
                    context.user_data.update({"page": 0})

            await self.send_venue_list(
                update, context, radius=context.user_data["radius"]
            )

        elif query.data.startswith("notion_"):
            notion_id = query.data.split("_")[1]

            company = get_place_by_id(int(notion_id))
            context.user_data["current_card"] = company

            await self.show_place_card(
                update, context, company=company, edit_state=True
            )

        return 3

    async def button_state_handler(
        self, update: Update, context: CallbackContext
    ) -> NoReturn:
        """
        Handles the 'edit_place_card' callback.

        Args:
            update (Update): The update object containing the incoming message.
            context (CallbackContext): The context from the update.
        """
        query = update.callback_query
        await query.answer()

        await self.show_editbar(update, context)
        await self.show_edit_keyboard(update, context)

    async def exit_location(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        context.user_data.clear()

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Showing radius list has been stopped, now send /start",
        )
        return ConversationHandler.END

    async def cancel_location(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> ConversationHandler.END:
        """
        Fallback of ConversationHandler.

        Args:
            update (Update): The update object containing the incoming message.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """

        context.user_data.clear()

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Showing radius list has been stopped, now send /start",
        )
        return ConversationHandler.END

    def start_bot(self):
        """Starts the bot by setting up handlers and running polling."""
        logger.info("Starting bot...")

        start_handler = CommandHandler("start", self.start)

        button_handler_instance = CallbackQueryHandler(
            self.button_handler, pattern="^button_add_pressed$"
        )

        show_unfilled_handler = CallbackQueryHandler(
            self.show_unfilled_places, pattern="^show_unfilled_places$"
        )

        button_instance = CallbackQueryHandler(
            self.button,
            pattern="^(Name|type|google_map|phone_number|whatsapp|manager_phone_number|hours_of_operation|Places to eat|Adventures|Services)$",
        )

        exit_handler = MessageHandler(filters.Regex("^Exit$"), self.handle_exit)
        save_handler = MessageHandler(filters.Regex("^Save$"), self.handle_save)

        company_name_handler = MessageHandler(
            filters.REPLY & filters.TEXT, self.handle_company_name
        )

        show_info_handler = MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_new_value
        )

        edit_card_handler = CallbackQueryHandler(
            self.button_state_handler, pattern="edit_place_card"
        )

        location_conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.LOCATION, self.handle_location)],
            states={
                1: [
                    CallbackQueryHandler(
                        self.photo_callback, pattern="photo_true|photo_false"
                    )
                ],
                2: [
                    MessageHandler(filters.TEXT, self.take_radius),
                    CallbackQueryHandler(self.exit_location, pattern="^exit_location$"),
                ],
                3: [
                    CallbackQueryHandler(
                        self.prev_next_button,
                        pattern="^notion_\d+$|page_next|page_prev",
                    ),
                    CallbackQueryHandler(self.exit_location, pattern="^exit_location$"),
                ],
            },
            fallbacks=[CommandHandler("cancel_location", self.cancel_location)],
            per_user=True,
            per_chat=True,
        )

        photo_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.add_photo, pattern="photo")],
            states={1: [MessageHandler(filters.PHOTO, self.photo_handler)]},
            fallbacks=[CommandHandler("finish", self.finish_photo)],
            per_user=True,
            per_chat=True,
        )

        select_company_handler = CallbackQueryHandler(
            self.select_company, pattern="^select_company_"
        )

        self.application.add_handler(start_handler)
        self.application.add_handler(button_handler_instance)
        self.application.add_handler(show_unfilled_handler)
        self.application.add_handler(button_instance)
        self.application.add_handler(exit_handler)
        self.application.add_handler(save_handler)
        self.application.add_handler(edit_card_handler)
        self.application.add_handler(location_conv_handler)
        self.application.add_handler(company_name_handler)
        self.application.add_handler(show_info_handler)
        self.application.add_handler(photo_conv_handler)
        self.application.add_handler(select_company_handler)

        try:
            self.application.run_polling()
        except RuntimeError as e:
            logger.error(f"Failed to stop the event loop gracefully: {e}")
