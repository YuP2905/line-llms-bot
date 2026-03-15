from typing import List, Optional, TypedDict
from asyncio import Lock

class MESSAGE_DATA(TypedDict):
    text: str
    image: Optional[bytes]
    video: Optional[bytes]
    reply_token: str
    lock: Lock
    active: bool

class SESSION_DATA(TypedDict):
    last_active: float
    history: List[str]
    vision_context: str