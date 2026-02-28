from fastapi import APIRouter, Request, Header, BackgroundTasks,  status
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

from core.config import settings

line_bot_router = APIRouter()
HANDLER = WebhookHandler(settings.LINE_CHANNEL_SECRET)
CONFIGURATION = Configuration(
    access_token=settings.LINE_CHANNEL_ACCESS_TOKEN
)

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
            HANDLER.handle, #type: ignore
            body,
            x_line_signature
        )
    except InvalidSignatureError:
        return {"message": "Invalid signature"}, status.HTTP_400_BAD_REQUEST
    return {"message": "OK"}, status.HTTP_200_OK