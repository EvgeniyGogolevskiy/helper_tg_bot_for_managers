import logging
from pydantic import BaseModel


class Data(BaseModel):
    """Formating class for update data"""

    name: str
    tp: str = ""
    photo: str = ""


class PlaceCard(Data):
    """Formating class for place card"""

    id: int
    guider_link: str = ""
    tag: str = ""
    description: str = ""
    network: str = ""
    firebase: str = ""
    location: str = ""
    google_map: str = ""
    waze: str = ""
    phone_number: str = ""
    whatsapp: str = ""
    role: str = ""
    email: str = ""
    address: str = ""
    hours_of_operation: str = ""
    link: str = ""
    comment: str = ""
