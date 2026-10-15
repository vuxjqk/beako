from src.schemas.base import CamelModel


class MessageResponse(CamelModel):
    message: str
