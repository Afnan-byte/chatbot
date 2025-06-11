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

class Form(StatesGroup):
    ready = State()
    searching = State()

waiting_users = {}
chat_pairs = {}

WELCOME_MESSAGES = [
    "🌟 Welcome to ChatConnect! Ready to meet someone new? Click below to begin."
]

CONNECTION_MESSAGES = [
    "🎉 You've been connected with a partner! Start chatting now.",
    "✨ You're now in a chat! Say hello."
]

SEARCHING_WARNING = "⏳ You're searching for a partner. Please wait..."

main_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_kb.row(types.KeyboardButton("🔍 Find Partner"))
main_menu_kb.row(types.KeyboardButton("ℹ️ Help"))

searching_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
searching_kb.row(types.KeyboardButton("❌ Cancel Search"))

chatting_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
chatting_kb.row(types.KeyboardButton("❌ End Chat"), types.KeyboardButton("🔁 Another User"))
chatting_kb.row(types.KeyboardButton("ℹ️ Help"))

HELP_TEXT = """
<b>🤝 ChatConnect Help</b>

<u>📌 How to Use:</u>
1. Press <b>🔍 Find Partner</b> to connect
2. Chat freely
3. End chat any time with <b>❌ End Chat</b>

<u>🔧 Menu Options:</u>
🔍 Find Partner - Start searching
❌ Cancel Search - Stop search
❌ End Chat - End your chat
🔁 Another User - End current & find new
ℹ️ Help - Show help
"""

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
        await message.answer("🔍 Searching for a partner...", reply_markup=searching_kb)
        await Form.searching.set()

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in chat_pairs:
        partner_id = chat_pairs.pop(user_id)
        if partner_id in chat_pairs:
            chat_pairs.pop(partner_id)
            await bot.send_message(partner_id, "⚠️ Your partner disconnected.", reply_markup=main_menu_kb)

    await Form.ready.set()
    await message.answer(random.choice(WELCOME_MESSAGES), reply_markup=main_menu_kb)

@dp.message_handler(text="🔍 Find Partner", state=Form.ready)
async def find_partner(message: types.Message):
    await search_for_partner(message.from_user.id, message)

@dp.message_handler(text="❌ Cancel Search", state=Form.searching)
async def cancel_search(message: types.Message):
    user_id = message.from_user.id
    waiting_users.pop(user_id, None)
    await message.answer("❌ Search canceled.", reply_markup=main_menu_kb)
    await Form.ready.set()

@dp.message_handler(text="❌ End Chat", state=Form.ready)
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    partner_id = chat_pairs.pop(user_id, None)
    if partner_id:
        chat_pairs.pop(partner_id, None)
        await bot.send_message(partner_id, "⚠️ Chat ended by your partner.", reply_markup=main_menu_kb)
    await message.answer("✅ Chat ended.", reply_markup=main_menu_kb)

@dp.message_handler(text="🔁 Another User", state=Form.ready)
async def another_user(message: types.Message):
    await end_chat(message)
    await search_for_partner(message.from_user.id, message)

@dp.message_handler(text="ℹ️ Help", state="*")
async def show_help(message: types.Message):
    state = await dp.current_state(user=message.from_user.id).get_state()
    reply_markup = chatting_kb if message.from_user.id in chat_pairs else main_menu_kb
    await message.answer(HELP_TEXT, reply_markup=reply_markup)

@dp.message_handler(state=Form.searching, content_types=types.ContentType.ANY)
async def block_while_searching(message: types.Message):
    await message.reply(SEARCHING_WARNING)

@dp.message_handler(state=Form.ready, content_types=types.ContentType.ANY)
async def relay_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in chat_pairs:
        await message.answer("ℹ️ You are not in a chat. Use 🔍 Find Partner.", reply_markup=main_menu_kb)
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
        logger.error(f"Relay error: {e}")
        chat_pairs.pop(user_id, None)
        if partner_id:
            chat_pairs.pop(partner_id, None)
            await bot.send_message(partner_id, "⚠️ Chat ended due to disconnection.", reply_markup=main_menu_kb)
        await message.answer("⚠️ Partner disconnected.", reply_markup=main_menu_kb)

if __name__ == '__main__':
    logger.info("Bot is starting...")
    executor.start_polling(dp, skip_updates=True)
