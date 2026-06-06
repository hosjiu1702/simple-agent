import asyncio
import os
from os import path as osp
from pprint import pprint
from dotenv import load_dotenv
from flask import Flask, request
from zalo_bot import Update, Bot
from zalo_bot.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext,
    Dispatcher
)
from zalo_bot.constants import ChatAction
from agents import SQLiteSession, SessionSettings
from src.agent import NewsAgent
from src.settings import init_global_settings
from src import settings


load_dotenv()
bot = Bot(token=os.getenv("ZALO_BOT_TOKEN"))
bot.set_webhook(url=os.getenv("WEBHOOK_URL"), secret_token=os.getenv("SECRET_TOKEN"))

app = Flask(__name__)
init_global_settings()

# Init main agent
news_agent = NewsAgent(debug=True)

# CONVERSATION HISTORY DATABASE
# Session ID for accessing to old previous messages (persistent memory?)
CONVERSATION_DB = "conversation.db"
os.makedirs("database", exist_ok=True)
conversation_db = osp.join("database", CONVERSATION_DB)

# session_id = "conversation_170296"
# conversation_db = "database/conversation.db"
# session = SQLiteSession(session_id, conversation_db)


async def reply_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # await update.message.reply_text(f"You just said: {update.message.text}")
    print("[DEBUG][server.py] The agent is thinking...")

    # Get conversation history according to the user chat id
    chat_id = update.message.chat.id
    session_id = f"session_id_{chat_id}"
    session = SQLiteSession(session_id, conversation_db)
    print(f"[DEBUG][server.py] session_id: {session_id}")

    # Typing effect
    await context.bot.send_chat_action(
        chat_id=chat_id,
        action=ChatAction.TYPING
    )
    await asyncio.sleep(3)

    # LLM inference
    response = await news_agent.reply(
        query=update.message.text, session=session,
        chat_id=chat_id, zalo_bot=bot
    )

    # bring the above response back to the zalo user
    await update.message.reply_text(response)
    print(f"Agent responded: {response}")


async def confirm_ride_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[DEBUG][confirm_ride_booking] Called.")
    print(f"[DEBUG][confirm_ride_booking][settings.pending] = {settings.pending}")
    chat_id = update.message.chat.id
    message = update.message.text

    if settings.pending.get(chat_id, None) is None:
        return

    print(f"[DEBUG][confirm_ride_booking] chat_id = {chat_id}")
    settings.decisions[chat_id] = True
    settings.pending[chat_id].set()


async def cancel_ride_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[DEBUG][cancel_ride_booking] Called.")
    print(f"[DEBUG][cancel_ride_booking][settings.pending] = {settings.pending}")
    chat_id = update.message.chat.id
    message = update.message.text

    if settings.pending.get(chat_id, None) is None:
        return

    print(f"[DEBUG][cancel_ride_booking] chat_id = {chat_id}")
    settings.decisions[chat_id] = False
    settings.pending[chat_id].set()


# async def reply_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     caption = update.message.api_kwargs.get("caption", "")
#     photo_url = update.message.api_kwargs.get("photo_url", "")

#     print("[DEBUG][server.py] Called reply_for_photo.")
#     pprint(f"[DEBUG][server.py] Received Message: {update.message}")
#     print(f"[DEBUG][server.py] Caption: {caption}")
#     print(f"[DEBUG][server.py] Photo URL: {photo_url}")
#     pprint(f"[DEBUG][server.py] Current Session: {await session.get_items()}")

#     # Typing effect
#     await context.bot.send_chat_action(
#         chat_id=update.message.chat.id,
#         action=ChatAction.TYPING
#     )
#     response = await news_agent.reply(query=caption, photo_url=photo_url, session=session)
#     await update.message.reply_text(response)


@app.route('/webhook', methods=['POST'])
def webhook():
    print("Webhook is called.")
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "WEBHOOK CALLED."


dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_user))
dispatcher.add_handler(CommandHandler("ok", confirm_ride_booking))
dispatcher.add_handler(CommandHandler("no", cancel_ride_booking))
# dispatcher.add_handler(MessageHandler(filters.PHOTO, reply_for_photo))

if __name__ == "__main__":
    print("Flask server started.")
    app.run(port=8443, debug=True)