from typing import List, Dict, cast

from fastapi import APIRouter, Request, Header, BackgroundTasks,  status
from fastapi.responses import JSONResponse

from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import (
    WebhookParser,
    WebhookPayload,
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
from linebot.v3.webhooks.models import Event
import asyncio
import time

from core.config import settings
from services.manager import model_manager
from apps.chat.callbacks import (
    qwen_chat_callback,
)
from apps.bot.typing import (
    MESSAGE_DATA,
    SESSION_DATA
)

line_bot_router = APIRouter()

parser = WebhookParser(settings.LINE_CHANNEL_SECRET.get_secret_value())
line_config = Configuration(
    access_token=settings.LINE_CHANNEL_ACCESS_TOKEN.get_secret_value()
)

##? Key: User ID
User_Message_Accumulator: Dict[
    str,
    MESSAGE_DATA
] = {}

User_Session_Buffer: Dict[
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
        events = cast(
            List[Event | WebhookPayload],
            parser.parse(             # pyright: ignore
                body_bytes.decode("utf-8"),
                x_line_signature
            )
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

async def handle_qwen_msg(
    event: MessageEvent
) -> None:
    global settings, line_config, model_manager
    global User_Message_Accumulator

    source = cast(UserSource | GroupSource | RoomSource, event.source)
    user_message = event.message
    user_message_id = user_message.id
    user_id = source.user_id
    source_type = source.type
    reply_token = cast(str, event.reply_token)

    Bot_name = settings.BOT_NAME

    # ~ Future Work
    if user_id not in User_Message_Accumulator:
        # Initialize Message Auccumulator for this user
        User_Message_Accumulator[user_id] = {
            "text": '',
            "image": None,
            "video": None,
            "reply_token": reply_token,
            "lock": asyncio.Lock(),
            "active": False
        }

    # ~ Future Work
    ##? Get the accumulator for this user, which will store the text, image, video and reply token until the message is processed after the delay
    Msg_Accum = User_Message_Accumulator[user_id]

    ##? If user sends text
    if isinstance(user_message, TextMessageContent):
        user_message_text = user_message.text # if in group/room, user_message_text ilcludes @

        ##? In group/room, check if bot is mentioned
        if source_type in ["group", "room"]:
            ##? b_name ===> @Bot_name
            b_name = '@' + Bot_name if not Bot_name.startswith('@') else Bot_name

            ##? If Bot is not mentioned, ignore the message and cleanup
            if b_name not in user_message_text:
                if not Msg_Accum["active"]:
                    User_Message_Accumulator.pop(user_id, None)
                return

            ##? If Bot is mentioned, extract text without bot name
            user_msg_text = None if not user_message_text else user_message_text.replace(b_name, '').strip()

        else:
            # Private chat, use all text
            user_msg_text = user_message_text.strip()

        if user_msg_text:
            Msg_Accum["text"] = f"{Msg_Accum['text']} {user_msg_text}".strip()
            Msg_Accum["reply_token"] = reply_token

    ##? elif user sends image or video
    elif isinstance(user_message, (ImageMessageContent, VideoMessageContent)):
        ##! Only support image or video without text in Line
        ##! But here Usr_accm["text"] to store the extracted text from the message, which will be used as the prompt for Qwen when vision data is present.
        if source_type in ["group", "room"]:
            # Cleanup if not actively accumulating to prevent memory leak
            if not Msg_Accum["active"]:
                User_Message_Accumulator.pop(user_id, None)
            return

        Msg_Accum["reply_token"] = reply_token

        with ApiClient(line_config) as api_client:
            blob_api = MessagingApiBlob(api_client)
            loop = asyncio.get_event_loop()
            blob_data = cast(bytearray, await loop.run_in_executor(
                None,
                blob_api.get_message_content, # type: ignore
                user_message_id
            ))

            if isinstance(user_message, ImageMessageContent):
                Msg_Accum["image"] = blob_data
            else:
                Msg_Accum["video"] = blob_data

    if Msg_Accum["active"]:
        return

    async with Msg_Accum["lock"]:
        Msg_Accum["active"] = True
        await asyncio.sleep(settings.SLEEP_TIME)
        Msg_Data_Val = User_Message_Accumulator.pop(user_id, None)
        if not Msg_Data_Val:
            return
        await merge_message_process(
            event,
            user_id,
            Msg_Data_Val, # type: ignore
        )

async def merge_message_process(
    event: MessageEvent,
    user_id: str,
    message_data: MESSAGE_DATA,
):
    global settings, line_config, model_manager
    global User_Session_Buffer

    session_timeout = settings.SESSION_TIMEOUT
    max_history = settings.MAX_HISTORY
    bot_name = settings.BOT_NAME
    gpu_crash_msg = settings.GPU_CRASH_MSG
    code_refining_msg = settings.CODE_REFINING_MSG

    now = time.time()

    if user_id in User_Session_Buffer:
        Last_active = User_Session_Buffer[user_id]["last_active"]
        if now - Last_active > session_timeout:
            User_Session_Buffer.pop(user_id)

    if user_id not in User_Session_Buffer:
        User_Session_Buffer[user_id] = {
            "last_active": now,
            "history": [],
            "vision_context": ''
        }

    Session_Data = User_Session_Buffer[user_id]
    Session_Data["last_active"] = now

    user_text = message_data["text"]
    image_bytes = message_data["image"]
    video_bytes = message_data["video"]
    reply_token = message_data["reply_token"]

    try:
        if image_bytes or video_bytes:
            if not user_text:
                user_text = "Please describe this."
            Session_Data["vision_context"] = '' # Clear vision context when new message comes, and update it after getting AI reply
        else:
            Vision_Context = Session_Data["vision_context"]
            History = Session_Data.get("history", [])
            History = "\n".join(History[-max_history * 2:]) # Only keep recent history within the limit

            if Vision_Context or History:
                user_text = (
                    f"<Vision_Context>\n{Vision_Context}\n</Vision_Context>\n\n"
                    f"<Chat_History>\n{History}\n</Chat_History>\n\n"
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
                Session_Data["vision_context"] = ai_reply
            else:
                History_list = Session_Data["history"]
                History_list.append(f"User: {message_data['text']}")
                History_list.append(f"{bot_name}: {ai_reply}")

                if len(History_list) > settings.MAX_HISTORY * 2:
                    Session_Data["history"] = History_list[-settings.MAX_HISTORY * 2:]
        else:
            ai_reply = "Sorry! No response generated. Plz try again with a different message."

    except Exception as e:
        if "CUDA out of memory" in str(e):
            ai_reply = (
                f"{gpu_crash_msg}"
            )
        else:
            ai_reply = (
                f"Sorry! {bot_name} Service Unavailable:\n"
                f"{str(e)}\n"
                f"{code_refining_msg}"
            )

    with ApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=ai_reply)]
            )
        )
