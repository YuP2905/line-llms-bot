from typing import cast
from fastapi import APIRouter, Request, Header, BackgroundTasks,  status
from fastapi.responses import JSONResponse

from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import google.generativeai as genai
# from google.generativeai.types import GenerateContentResponse

from core.config import settings

line_bot_router = APIRouter()
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
line_config = Configuration(
    access_token=settings.LINE_CHANNEL_ACCESS_TOKEN
)

genai.configure(api_key=settings.GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

@line_bot_router.post(
    "/webhook"
)
async def line_bot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str|None = Header(None)
):
    body = await request.body()
    body = body.decode("utf-8")
    try:
        background_tasks.add_task(
            handler.handle, #type: ignore
            body,
            x_line_signature
        )
    except InvalidSignatureError:
        return JSONResponse(
            content={"message": "Invalid signature"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return JSONResponse(
        content={"message": "OK"},
        status_code=status.HTTP_200_OK
    )

@handler.add(
    MessageEvent,
    message=TextMessageContent
)
def handle_text_msg(
    event: MessageEvent
):
    user_msg = cast(TextMessageContent, event.message).text
    source_type = event.source.type  # type:ignore
    bot_name = settings.BOT_NAME

    if source_type in ["group", "room"]:
        if bot_name not in user_msg:
            return
        user_msg = user_msg.replace(bot_name, '').strip()

    if not user_msg:
        return

    ai_reply: str = ''
    try:
        response = gemini_model.generate_content(user_msg)
        if response.text:
            ai_reply = response.text
        else:
            ai_reply = "Sorry, I need to slow down."

    except Exception as e:
        ai_reply = f"{bot_name} Service Unavailable: {str(e)}"

    with ApiClient(line_config) as api_client:
            line_bot_api: MessagingApi = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=ai_reply)]
                )
            )
