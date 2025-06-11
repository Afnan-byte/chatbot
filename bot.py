from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
import random
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# FSM States
class Form(StatesGroup):
    ready = State()

# Store user data
waiting_users = {}
chat_pairs = {}

# Keyboards
start_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
start_menu_kb.row(types.KeyboardButton("🔍 Search User"))

searching_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
searching_kb.row(types.KeyboardButton("❌ End Search"))

chat_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
chat_kb.row(types.KeyboardButton("❌ End Chat"))
chat_kb.row(types.KeyboardButton("🔄 Another User"), types.KeyboardButton("ℹ️ Help"))

after_chat_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
after_chat_kb.row(types.KeyboardButton("🔍 Search User"), types.KeyboardButton("ℹ️ Help"))

HELP_TEXT = """
<b>🤝 Help</b>

🔹 Use <b>🔍 Search User</b> to find someone to chat with.
🔹 Use <b>❌ End Chat</b> to disconnect.
🔹 Use <b>🔄 Another User</b> to switch to a new chat.
"""

# Start command
@dp.message_handler(commands=['start', 'restart'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in chat_pairs:
        partner_id = chat_pairs.pop(user_id)
        chat_pairs.pop(partner_id, None)
        await bot.send_message(partner_id, "⚠️ Your partner has disconnected.", reply_markup=after_chat_kb)
    await Form.ready.set()
    await message.answer("👋 Welcome to ChatConnect!\nPress 🔍 Search User to begin.", reply_markup=start_menu_kb)

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT, reply_markup=after_chat_kb)

# Button Handlers
@dp.message_handler(text="🔍 Search User", state=Form.ready)
async def search_user(message: types.Message):
    user_id = message.from_user.id
    if user_id in chat_pairs:
        await message.answer("⚠️ You're already in a chat.", reply_markup=chat_kb)
        return

    for uid in list(waiting_users.keys()):
        if uid != user_id and uid not in chat_pairs:
            chat_pairs[user_id] = uid
            chat_pairs[uid] = user_id
            waiting_users.pop(uid, None)
            await bot.send_message(user_id, "✅ You’re now connected to a user. Say hi!", reply_markup=chat_kb)
            await bot.send_message(uid, "✅ You’re now connected to a user. Say hi!", reply_markup=chat_kb)
            return

    waiting_users[user_id] = True
    await message.answer("⏳ Searching for a partner...", reply_markup=searching_kb)

@dp.message_handler(text="❌ End Search", state=Form.ready)
async def end_search(message: types.Message):
    user_id = message.from_user.id
    if waiting_users.pop(user_id, None):
        await message.answer("❌ Search cancelled.", reply_markup=start_menu_kb)
    else:
        await message.answer("⚠️ You are not in search mode.", reply_markup=start_menu_kb)

@dp.message_handler(text="❌ End Chat", state=Form.ready)
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    partner_id = chat_pairs.pop(user_id, None)
    if partner_id:
        chat_pairs.pop(partner_id, None)
        await bot.send_message(partner_id, "🚫 The user has ended the chat.", reply_markup=after_chat_kb)
    await message.answer("✅ Chat ended.", reply_markup=after_chat_kb)

@dp.message_handler(text="🔄 Another User", state=Form.ready)
async def another_user(message: types.Message):
    user_id = message.from_user.id
    partner_id = chat_pairs.pop(user_id, None)
    if partner_id:
        chat_pairs.pop(partner_id, None)
        await bot.send_message(partner_id, "🔁 The user is looking for a new chat.", reply_markup=after_chat_kb)
    await search_user(message)

@dp.message_handler(text="ℹ️ Help", state='*')
async def show_help(message: types.Message):
    await cmd_help(message)

# Message forwarding
@dp.message_handler(state=Form.ready, content_types=types.ContentType.ANY)
async def forward_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in chat_pairs:
        await message.answer("🧍 You are not in a chat.\nPress 🔍 Search User to connect.", reply_markup=start_menu_kb)
        return

    partner_id = chat_pairs.get(user_id)
    try:
        if message.text:
            await bot.send_message(partner_id, message.text)
        elif message.sticker:
            await bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.photo:
            await bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption or "")
        elif message.video:
            await bot.send_video(partner_id, message.video.file_id, caption=message.caption or "")
        elif message.voice:
            await bot.send_voice(partner_id, message.voice.file_id)
        else:
            await message.reply("⚠️ Unsupported message type.")
    except Exception as e:
        logger.error(f"Message forwarding error: {e}")
        chat_pairs.pop(user_id, None)
        chat_pairs.pop(partner_id, None)
        await message.answer("⚠️ Partner disconnected.", reply_markup=after_chat_kb)

# Run the bot
if __name__ == '__main__':
    logger.info("Bot is running...")
    executor.start_polling(dp, skip_updates=True)
