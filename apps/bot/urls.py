from typing import List, Dict, Optional, TypedDict, cast
from asyncio import Lock

from fastapi import APIRouter, Request, Header, BackgroundTasks,  status
from fastapi.responses import JSONResponse

from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
)

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    UserSource,
    GroupSource,
    RoomSource
)
import asyncio
import time

from core.config import settings
from services.manager import model_manager
from apps.chat.callbacks import (
    qwen_chat_callback,
)

line_bot_router = APIRouter()

parser = WebhookParser(settings.LINE_CHANNEL_SECRET)
line_config = Configuration(
    access_token=settings.LINE_CHANNEL_ACCESS_TOKEN
)

##? Key: User ID
class MESSAGE_DATA(TypedDict):
    text: str
    image: Optional[bytes]
    video: Optional[bytes]
    reply_token: str
    lock: Lock
    active: bool
MESSAGE_ACCUMULATOR: Dict[
    str,
    MESSAGE_DATA
] = {}

class SESSION_DATA(TypedDict):
    last_active: float
    history: List[str]
    vision_context: str
SESSION_BUFFER: Dict[
    str,
    SESSION_DATA
] = {}

@line_bot_router.post(
    "/webhook"
)
async def line_bot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str | None = Header(None)
) -> JSONResponse:
    if x_line_signature is None:
        return JSONResponse(
            content={"message": "Missing signature"},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    body_bytes: bytes = await request.body()

    try:
        events: list = parser.parse(
            body_bytes.decode("utf-8"),
            x_line_signature
        )
    except InvalidSignatureError:
        return JSONResponse(
            content={"message": "Invalid signature"},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    for event in events:
        if isinstance(event, MessageEvent):
            if isinstance(event.message, (TextMessageContent, ImageMessageContent, VideoMessageContent)):
                background_tasks.add_task(handle_qwen_msg, event)

    return JSONResponse(
        content={"message": "OK"},
        status_code=status.HTTP_200_OK
    )

def extract_message_text(
    user_text: Optional[str],
    source_type: str,
    bot_name: str
) -> Optional[str]:

    if not user_text:
        return ''

    #? If in group or room, check if the bot is mentioned, and remove the bot name from the message
    if source_type in ["group", "room"]:
        b_name  = '@' + bot_name if not bot_name.startswith('@') else bot_name
        if b_name not in user_text:
            return
        return user_text.replace(b_name, '').strip()

    return user_text.strip()

async def handle_qwen_msg(
    event: MessageEvent
) -> None:
    global settings, line_config, model_manager

    source = cast(UserSource | GroupSource | RoomSource, event.source)
    user_message = event.message
    user_id = source.user_id
    source_type = source.type
    reply_token = cast(str, event.reply_token)

    bot_name = settings.BOT_NAME

    if user_id not in MESSAGE_ACCUMULATOR:
        MESSAGE_ACCUMULATOR[user_id] = {
            "text": '',
            "image": None,
            "video": None,
            "reply_token": reply_token,
            "lock": asyncio.Lock(),
            "active": False
        }

    accum = MESSAGE_ACCUMULATOR[user_id]


    ##? If user sends text
    if isinstance(user_message, TextMessageContent):
        user_text = user_message.text
        user_text = extract_message_text(user_text, source_type, bot_name)

        if user_text:
            accum["text"] = f"{accum['text']} {user_text}".strip()
            accum["reply_token"] = reply_token

    ##? elif user sends image or video
    elif isinstance(user_message, (ImageMessageContent, VideoMessageContent)):
        ##~ Temporaty: Only support image or video without text in pribate chat
        ##~ Future: Support image or video with text, and support image or video in group or room chat
        if source_type in ["group", "room"]:
            return

        accum["reply_token"] = reply_token

        with ApiClient(line_config) as api_client:
            blob_api = MessagingApiBlob(api_client)
            loop = asyncio.get_event_loop()
            blob_data =cast(bytearray, await loop.run_in_executor(
                None,
                blob_api.get_message_content, # type: ignore
                user_message.id
            ))

            if isinstance(user_message, ImageMessageContent):
                accum["image"] = blob_data
            else:
                accum["video"] = blob_data

    if accum["active"]:
        return

    async with accum["lock"]:
        accum["active"] = True
        await asyncio.sleep(settings.SLEEP_TIME)
        message_data = MESSAGE_ACCUMULATOR.pop(user_id)
        await merge_message_process(
            event,
            user_id,
            message_data,
            bot_name
        )

async def merge_message_process(
    event: MessageEvent,
    user_id: str,
    message_data: MESSAGE_DATA,
    bot_name: str = settings.BOT_NAME
):
    global settings, line_config, model_manager

    now = time.time()

    if user_id in SESSION_BUFFER:
        last_active = SESSION_BUFFER[user_id]["last_active"]
        if now - last_active > settings.SESSION_TIMEOUT:
            SESSION_BUFFER.pop(user_id)

    if user_id not in SESSION_BUFFER:
        SESSION_BUFFER[user_id] = {
            "last_active": now,
            "history": [],
            "vision_context": ''
        }

    session = SESSION_BUFFER[user_id]
    session["last_active"] = now

    user_text = message_data["text"]
    image_bytes = message_data["image"]
    video_bytes = message_data["video"]
    reply_token = message_data["reply_token"]

    try:
        if image_bytes or video_bytes:
            if not user_text:
                user_text = "Please describe this."
            session["vision_context"] = '' # Clear vision context when new message comes, and update it after getting AI reply
        else:
            vision_context = session["vision_context"]
            history = session.get("history", [])
            history = "\n".join(history[-settings.MAX_HISTORY * 2:]) # Only keep recent history within the limit

            if vision_context or history:
                user_text = (
                    f"<Vision_Context>\n{vision_context}\n</Vision_Context>\n\n"
                    f"<Chat_History>\n{history}\n</Chat_History>\n\n"
                    f"<Current_Message>\n{user_text}\n</Current_Message>\n\n"
                    "### SYSTEM_RESTRICTION ###\n"
                    "1. LANGUAGE_MATCH: You MUST identify the language of <Current_Message> first. "
                    "Your entire response MUST be written in that EXACT same language.\n"
                    "2. CONTEXT_RELEVANCE: Evaluate if <Current_Message> is linked to the provided context. "
                    "If yes, respond based on context; if no, ignore background data.\n"
                    "3. NO_EXCEPTIONS: Do not use the language of Vision_Context or Chat_History "
                    "unless it matches <Current_Message>."
                )

        ai_reply = await model_manager.safe_inference(
            "qwen_multi",
            qwen_chat_callback,
            prompt=user_text,
            image_data=image_bytes,
            video_data=video_bytes
        )

        if ai_reply:
            if image_bytes or video_bytes:
                session["vision_context"] = ai_reply
            else:
                history_list = session["history"]
                history_list.append(f"User: {message_data['text']}")
                history_list.append(f"{bot_name}: {ai_reply}")

                if len(history_list) > settings.MAX_HISTORY * 2:
                    session["history"] = history_list[-settings.MAX_HISTORY * 2:]
        else:
            ai_reply = "Sorry! No response generated. Plz try again with a different message."

    except Exception as e:
        if "CUDA out of memory" in str(e):
            ai_reply = (
                f"{settings.GPU_CRASH_MSG}"
            )
        else:
            ai_reply = (
                f"Sorry! {bot_name} Service Unavailable:\n"
                f"{str(e)}\n"
                f"{settings.CODE_REFINING_MSG}"
            )

    with ApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=ai_reply)]
            )
        )
