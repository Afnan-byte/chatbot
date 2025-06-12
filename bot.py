from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
import os
import random
from dotenv import load_dotenv

# Load token
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# States
class Form(StatesGroup):
    ready = State()
    searching = State()

# Data
waiting_users = {}
chat_pairs = {}

# Keyboards
main_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_kb.add(types.KeyboardButton("🎲 Start"), types.KeyboardButton("❓ Help"))

searching_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
searching_kb.add(types.KeyboardButton("⛔ Stop"))

chatting_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
chatting_kb.row(types.KeyboardButton("⏭️ Next"), types.KeyboardButton("⛔ Stop"))
chatting_kb.add(types.KeyboardButton("❓ Help"))

# Messages
WELCOME_MSG = "👋 Welcome to <b>ChatConnect</b>\n\nPress 🎲 <b>Start</b> to chat anonymously with someone!"
HELP_TEXT = """
<b>🤖 ChatConnect Bot Help</b>

<b>🎲 Start</b> - Find a new anonymous partner  
<b>⏭️ Next</b> - End current chat and find a new one  
<b>⛔ Stop</b> - End current chat  
<b>❓ Help</b> - Show this help message
"""

CONNECTION_MESSAGES = [
    "💬 You're now connected anonymously. Say hi!",
    "🎉 Chat started! Feel free to talk."
]

SEARCHING_WARNING = "⏳ You're already searyyyyching. Please wait to be connected."

# Handlers
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in chat_pairs:
        partner_id = chat_pairs.pop(user_id, None)
        if partner_id:
            chat_pairs.pop(partner_id, None)
            await bot.send_message(partner_id, "⚠️ Your partner disconnected.", reply_markup=main_menu_kb)
    await Form.ready.set()
    await message.answer(WELCOME_MSG, reply_markup=main_menu_kb)

@dp.message_handler(commands=['help'])
@dp.message_handler(text="❓ Help", state="*")
async def cmd_help(message: types.Message):
    reply_kb = chatting_kb if message.from_user.id in chat_pairs else main_menu_kb
    await message.answer(HELP_TEXT, reply_markup=reply_kb)

@dp.message_handler(commands=['stop'])
@dp.message_handler(text="⛔ Stop", state="*")
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    partner_id = chat_pairs.pop(user_id, None)
    if partner_id:
        chat_pairs.pop(partner_id, None)
        await bot.send_message(partner_id, "❌ Your chat has ended.", reply_markup=main_menu_kb)
    waiting_users.pop(user_id, None)
    await message.answer("✅ Chat ended.", reply_markup=main_menu_kb)
    await Form.ready.set()

@dp.message_handler(commands=['next'])
@dp.message_handler(text="⏭️ Next", state="*")
async def next_chat(message: types.Message):
    await end_chat(message)
    await message.answer("🔍 Searching for a new partner...", reply_markup=searching_kb)
    await search_for_partner(message.from_user.id)

@dp.message_handler(text="🎲 Start", state=Form.ready)
async def start_search(message: types.Message):
    await search_for_partner(message.from_user.id, message)

@dp.message_handler(text="⛔ Stop", state=Form.searching)
async def cancel_search(message: types.Message):
    waiting_users.pop(message.from_user.id, None)
    await message.answer("❌ Search canceled.", reply_markup=main_menu_kb)
    await Form.ready.set()

@dp.message_handler(state=Form.searching, content_types=types.ContentType.ANY)
async def block_while_searching(message: types.Message):
    await message.reply(SEARCHING_WARNING)

async def search_for_partner(user_id: int, message: types.Message = None):
    if user_id in chat_pairs:
        if message:
            await message.answer("⚠️ You're already in a chat.", reply_markup=chatting_kb)
        return

    for uid in list(waiting_users.keys()):
        if uid != user_id and uid not in chat_pairs:
            chat_pairs[user_id] = uid
            chat_pairs[uid] = user_id
            waiting_users.pop(user_id, None)
            waiting_users.pop(uid, None)

            msg = random.choice(CONNECTION_MESSAGES)
            await bot.send_message(user_id, msg, reply_markup=chatting_kb)
            await bot.send_message(uid, msg, reply_markup=chatting_kb)
            await Form.ready.set()
            return

    if message:
        waiting_users[user_id] = True
        await message.answer("🔍 Looking for a partner...", reply_markup=searching_kb)
        await Form.searching.set()

@dp.message_handler(state=Form.ready, content_types=types.ContentType.ANY)
async def relay_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in chat_pairs:
        await message.answer("ℹ️ You are not in a chat. Use 🎲 Start.", reply_markup=main_menu_kb)
        return

    partner_id = chat_pairs.get(user_id)
    try:
        await bot.send_chat_action(partner_id, types.ChatActions.TYPING)
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
        elif message.document:
            await bot.send_document(partner_id, message.document.file_id, caption=message.caption or "")
        else:
            await message.reply("⚠️ Unsupported message type.")
    except Exception as e:
        logger.error(f"Relay error: {e}")
        chat_pairs.pop(user_id, None)
        if partner_id:
            chat_pairs.pop(partner_id, None)
            await bot.send_message(partner_id, "⚠️ Partner disconnected.", reply_markup=main_menu_kb)
        await message.answer("⚠️ Partner disconnected.", reply_markup=main_menu_kb)

# Run the bot
if __name__ == '__main__':
    logger.info("Bot is starting...")
    executor.start_polling(dp, skip_updates=True)
