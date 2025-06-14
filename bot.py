from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import BotBlocked, ChatNotFound, UserDeactivated
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# States
class ChatState(StatesGroup):
    idle = State()
    searching = State()
    chatting = State()

# Data storage
waiting_users = []
active_pairs = {}

# Keyboards
def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("🚀 Start Chat"))
    keyboard.add(types.KeyboardButton("ℹ️ Help"))
    return keyboard

def get_searching_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("❌ Cancel Search"))
    return keyboard

def get_chatting_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("⏭️ Next Partner"))
    keyboard.add(types.KeyboardButton("⏹️ End Chat"))
    return keyboard

# Messages
WELCOME_MSG = """
👋 Welcome to <b>Anonymous Text Chat</b>!
📝 Only text messages are allowed.
🚀 Press <b>Start Chat</b> to begin!
"""

HELP_MSG = """
<b>📚 Help Guide</b>

<b>🚀 Start Chat</b> - Find a random partner  
<b>⏭️ Next Partner</b> - Skip to next partner  
<b>⏹️ End Chat</b> - End current chat  
<b>❌ Cancel Search</b> - Stop searching  

Only text messages are supported.
"""

# Handlers
@dp.message_handler(commands=['start', 'help'], state='*')
async def send_welcome(message: types.Message):
    user_id = message.from_user.id

    partner_id = active_pairs.get(user_id)
    if partner_id:
        active_pairs.pop(partner_id, None)
        try:
            await bot.send_message(partner_id, "⚠️ Your partner disconnected.", reply_markup=get_main_keyboard())
        except (BotBlocked, ChatNotFound, UserDeactivated) as e:
            logger.warning(f"Failed to notify partner {partner_id}: {e}")

    active_pairs.pop(user_id, None)
    if user_id in waiting_users:
        waiting_users.remove(user_id)

    await ChatState.idle.set()
    await message.answer(WELCOME_MSG, reply_markup=get_main_keyboard())

@dp.message_handler(text="ℹ️ Help", state='*')
async def show_help(message: types.Message):
    current_state = await dp.current_state(user=message.from_user.id).get_state()
    if current_state == ChatState.chatting.state:
        await message.answer(HELP_MSG, reply_markup=get_chatting_keyboard())
    elif current_state == ChatState.searching.state:
        await message.answer(HELP_MSG, reply_markup=get_searching_keyboard())
    else:
        await message.answer(HELP_MSG, reply_markup=get_main_keyboard())

@dp.message_handler(text="🚀 Start Chat", state=ChatState.idle)
async def start_search(message: types.Message):
    user_id = message.from_user.id

    if user_id in active_pairs:
        await message.answer("⚠️ You're already in a chat!", reply_markup=get_chatting_keyboard())
        return

    if user_id not in waiting_users:
        waiting_users.append(user_id)

    await ChatState.searching.set()
    await message.answer("🔍 Searching for a partner...", reply_markup=get_searching_keyboard())

    if len(waiting_users) >= 2:
        user1 = waiting_users.pop(0)
        user2 = waiting_users.pop(0)

        active_pairs[user1] = user2
        active_pairs[user2] = user1

        try:
            await bot.send_message(user1, "💬 You're now connected! Say hi!", reply_markup=get_chatting_keyboard())
            await bot.send_message(user2, "💬 You're now connected! Say hi!", reply_markup=get_chatting_keyboard())
        except (BotBlocked, ChatNotFound, UserDeactivated) as e:
            logger.warning(f"Failed to connect users {user1} and {user2}: {e}")
            active_pairs.pop(user1, None)
            active_pairs.pop(user2, None)
            await ChatState.idle.set()
            return

        await dp.current_state(chat=user1, user=user1).set_state(ChatState.chatting.state)
        await dp.current_state(chat=user2, user=user2).set_state(ChatState.chatting.state)

@dp.message_handler(text="❌ Cancel Search", state=ChatState.searching)
async def cancel_search(message: types.Message):
    user_id = message.from_user.id
    if user_id in waiting_users:
        waiting_users.remove(user_id)

    await ChatState.idle.set()
    await message.answer("❌ Search canceled.", reply_markup=get_main_keyboard())

@dp.message_handler(text="⏭️ Next Partner", state=ChatState.chatting)
async def next_partner(message: types.Message):
    user_id = message.from_user.id
    partner_id = active_pairs.get(user_id)

    if partner_id:
        active_pairs.pop(partner_id, None)
        try:
            await bot.send_message(partner_id, "⚠️ Your partner left the chat.", reply_markup=get_main_keyboard())
        except (BotBlocked, ChatNotFound, UserDeactivated) as e:
            logger.warning(f"Next Partner: {partner_id} error: {e}")

    active_pairs.pop(user_id, None)
    await start_search(message)

@dp.message_handler(text="⏹️ End Chat", state='*')
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    partner_id = active_pairs.get(user_id)

    if partner_id:
        active_pairs.pop(partner_id, None)
        try:
            await bot.send_message(partner_id, "❌ Chat ended by partner.", reply_markup=get_main_keyboard())
        except (BotBlocked, ChatNotFound, UserDeactivated) as e:
            logger.warning(f"End Chat: {partner_id} error: {e}")

    active_pairs.pop(user_id, None)
    if user_id in waiting_users:
        waiting_users.remove(user_id)

    await ChatState.idle.set()
    await message.answer("❌ Chat ended.", reply_markup=get_main_keyboard())

@dp.message_handler(state=ChatState.chatting, content_types=types.ContentTypes.TEXT)
async def forward_message(message: types.Message):
    user_id = message.from_user.id
    partner_id = active_pairs.get(user_id)

    if not partner_id:
        await message.answer("⚠️ No active partner found.", reply_markup=get_main_keyboard())
        await ChatState.idle.set()
        return

    try:
        await bot.send_message(partner_id, f"👤: {message.text}")
    except (BotBlocked, ChatNotFound, UserDeactivated) as e:
        logger.warning(f"Message Forward Failed: {e}")
        await message.answer("⚠️ Partner is unavailable. Ending chat.", reply_markup=get_main_keyboard())
        await end_chat(message)

@dp.message_handler(state=ChatState.chatting, content_types=types.ContentTypes.ANY)
async def block_non_text_chatting(message: types.Message):
    if message.content_type != 'text':
        await message.reply("❌ Only text messages are allowed!", reply_markup=get_chatting_keyboard())

@dp.message_handler(state=ChatState.searching, content_types=types.ContentTypes.ANY)
async def block_while_searching(message: types.Message):
    await message.reply("⏳ Please wait while we find you a partner...", reply_markup=get_searching_keyboard())

@dp.message_handler(content_types=types.ContentTypes.ANY, state='*')
async def block_global_non_text(message: types.Message):
    if message.content_type != 'text':
        await message.reply("❌ This bot only supports text messages.", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    print("✅ Bot is running...")
    executor.start_polling(dp, skip_updates=True)
