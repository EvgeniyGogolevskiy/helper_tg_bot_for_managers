from sqlalchemy import Column, Integer, String, Boolean
from core.db import Base


class ModelPlaceCard(Base):

    __tablename__ = "google_sheet_data"
    Name = Column(String, default="", name="Name")
    id_key = Column(Integer, primary_key=True, autoincrement=True, name="id_key")
    ID = Column(String, default="", name="ID")
    id_page = Column(String, default="", name="id_page")
    type = Column(String, default="", name="Type")
    # Web = Column(String, default="", name="Web")
    # guider_link = Column(String, default="", name="Link to Guider")
    # tag = Column(String, default="", name="Tag")
    # additional_information = Column(String, default="", name="Additional information")
    # description = Column(String, default="", name="Description")
    # network = Column(String, default="", name="Сетевой")
    # firebase = Column(String, default="", name="Есть в firebase")
    photo = Column(String, default="", name="Photo Google Drive")
    location = Column(String, default="", name="Location")
    google_map = Column(String, default="", name="Google Map")
    # waze = Column(String, default="", name="Waze")
    phone_number = Column(String, default="", name="Phone Number")
    whatsapp = Column(String, default="", name="WhatsApp Number")
    # role = Column(String, default="", name="Owner / Manager")
    # email = Column(String, default="", name="Email Address")
    hours_of_operation = Column(String, default="", name="Hours of Operation")
    # link = Column(String, default="", name="Link to their site")
    # menu = Column(String, default="", name="Menu")
    # comment = Column(String, default="", name="Comment")
    # notion_status = Column(String, default="", name="notion")
    coordinates = Column(String, default="", name="coordinates")
    data_manager = Column(String, default="", name="data_manager")
    manager_phone_number = Column(String, default="", name="Owner / Manager")
    is_new = Column(Boolean, default=False, name="is_new")
    is_updated = Column(Boolean, default=False, name="is_updated")

    def to_dict(self) -> dict:
        """
        Convert the ModelPlaceCard instance to a dictionary.

        Returns:
        Dict[str, str]: A dictionary representation of the ModelPlaceCard instance with selected attributes.
        """
        result = {}
        if self.Name:
            result["Name"] = self.Name
        if self.type:
            result["Type"] = self.type
        if self.photo:
            result["Photo Google Drive"] = self.photo
        if self.google_map:
            result["Google Map"] = self.google_map
        if self.phone_number:
            result["Phone Number"] = self.phone_number
        if self.whatsapp:
            result["WhatsApp Number"] = self.whatsapp
        if self.hours_of_operation:
            result["Hours of Operation"] = self.hours_of_operation
        if self.manager_phone_number:
            result["Owner / Manager"] = self.manager_phone_number
        if self.manager_phone_number:
            result["Location"] = self.location

        return result
