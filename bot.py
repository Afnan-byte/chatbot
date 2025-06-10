from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Conversation states
class Form(StatesGroup):
    waiting_for_gender = State()
    ready = State()

# User data storage
waiting_users = {}  # {user_id: {"gender": str, "name": str}}
chat_pairs = {}     # {user_id: partner_id}

# Messages
WELCOME_MESSAGES = [
    "🌟 Welcome to ChatConnect! Let's find you a partner.",
    "👋 Hello! Ready to meet someone new?",
    "💬 Hi there! Your next conversation starts here."
]

CONNECTION_MESSAGES = [
    "You've been connected! Start chatting 👋",
    "Found a partner for you! Say hi! 😊",
    "Connection successful! Start your chat."
]

# Keyboards
def get_gender_keyboard(current_gender=""):
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(
            "👨 Male" + (" ✅" if current_gender.lower() == "male" else ""),
            callback_data="gender_male"
        ),
        types.InlineKeyboardButton(
            "👩 Female" + (" ✅" if current_gender.lower() == "female" else ""),
            callback_data="gender_female"
        ),
        types.InlineKeyboardButton(
            "🧑 Other" + (" ✅" if current_gender.lower() == "other" else ""),
            callback_data="gender_other"
        )
    ]
    kb.add(*buttons)
    return kb

main_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_kb.row(types.KeyboardButton("🔍 Find Partner"))
main_menu_kb.row(types.KeyboardButton("⚙️ Settings"), types.KeyboardButton("ℹ️ Help"))

searching_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
searching_menu_kb.row(types.KeyboardButton("❌ Cancel Search"))

# Updated chatting menu with always-visible End Chat button
chatting_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
chatting_menu_kb.row(types.KeyboardButton("❌ End Chat"))
chatting_menu_kb.row(types.KeyboardButton("ℹ️ Help"))

HELP_TEXT = """
<b>🤝 ChatConnect Help</b>

<u>📌 How to Use:</u>
1. Press /start to begin
2. Select your gender
3. Use <b>🔍 Find Partner</b> to connect
4. Chat until you or your partner ends

<u>🔧 Commands:</u>
/start - Start or restart
/help - Show this message
/settings - Change your gender
/end - End current chat
"""

# Search function
async def search_for_partner(user_id: int, message: types.Message = None):
    if user_id in chat_pairs:
        if message:
            await message.answer("⚠️ You're already in a chat.", reply_markup=chatting_menu_kb)
        return

    # Find any available partner
    for uid in list(waiting_users.keys()):
        if uid != user_id and uid not in chat_pairs:
            # Create chat pair
            chat_pairs[user_id] = uid
            chat_pairs[uid] = user_id
            
            # Remove from waiting list
            waiting_users.pop(user_id, None)
            waiting_users.pop(uid, None)
            
            # Notify both users
            msg = random.choice(CONNECTION_MESSAGES)
            await bot.send_message(user_id, msg, reply_markup=chatting_menu_kb)
            await bot.send_message(uid, msg, reply_markup=chatting_menu_kb)
            return
    
    # If no partner found
    if message:
        if user_id not in waiting_users:
            chat = await bot.get_chat(user_id)
            waiting_users[user_id] = {
                "gender": waiting_users.get(user_id, {}).get("gender", "Not set"),
                "name": chat.full_name
            }
        await message.answer("🔍 Searching for a partner...", reply_markup=searching_menu_kb)

# Command handlers
@dp.message_handler(commands=['start', 'restart'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Clean up any existing connections
    if user_id in chat_pairs:
        partner_id = chat_pairs.pop(user_id)
        if partner_id in chat_pairs:
            chat_pairs.pop(partner_id)
            await bot.send_message(partner_id, "⚠️ Your partner has disconnected.", reply_markup=main_menu_kb)
    
    await Form.waiting_for_gender.set()
    await message.answer(random.choice(WELCOME_MESSAGES), reply_markup=types.ReplyKeyboardRemove())
    current_gender = waiting_users.get(user_id, {}).get("gender", "")
    await message.answer("Select your gender:", reply_markup=get_gender_keyboard(current_gender))

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    current_state = await dp.current_state(user=message.from_user.id).get_state()
    reply_markup = main_menu_kb
    
    if current_state == Form.ready.state and message.from_user.id in chat_pairs:
        reply_markup = chatting_menu_kb
    
    await message.answer(HELP_TEXT, reply_markup=reply_markup)

@dp.message_handler(commands=['settings'])
async def cmd_settings(message: types.Message):
    user_id = message.from_user.id
    if user_id not in waiting_users and user_id not in chat_pairs:
        await message.answer("Please use /start first.")
        return
    
    current_gender = waiting_users.get(user_id, {}).get("gender", "Not set")
    await message.answer(
        f"⚙️ <b>Settings</b>\n\nGender: {current_gender}\n\nChange your gender:",
        reply_markup=types.InlineKeyboardMarkup().row(
            types.InlineKeyboardButton("Change Gender", callback_data="change_gender")
        )
    )

# New /end command handler
@dp.message_handler(commands=['end'], state=Form.ready)
async def cmd_end(message: types.Message):
    await end_chat(message)

# Callback handlers
@dp.callback_query_handler(lambda c: c.data == "change_gender", state='*')
async def change_gender(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    current_gender = waiting_users.get(user_id, {}).get("gender", "")
    await bot.send_message(user_id, "Select your gender:", reply_markup=get_gender_keyboard(current_gender))

@dp.callback_query_handler(lambda c: c.data.startswith("gender_"), state='*')
async def process_gender(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    gender_map = {
        "gender_male": "Male",
        "gender_female": "Female",
        "gender_other": "Other"
    }
    gender = gender_map.get(callback_query.data, "Other")
    
    # Update user data
    chat = await bot.get_chat(user_id)
    waiting_users[user_id] = {
        "gender": gender,
        "name": chat.full_name
    }
    
    await bot.answer_callback_query(callback_query.id, f"Gender set to {gender}")
    
    try:
        await bot.edit_message_text(
            f"✅ Gender: {gender}",
            callback_query.message.chat.id,
            callback_query.message.message_id
        )
    except:
        await bot.send_message(user_id, f"✅ Gender: {gender}")
    
    if await state.get_state() == Form.waiting_for_gender.state:
        await Form.ready.set()
        await bot.send_message(
            user_id,
            "🌟 Setup complete!\nPress 🔍 Find Partner when ready!",
            reply_markup=main_menu_kb
        )
    else:
        # Return to settings
        temp_message = types.Message(
            chat=callback_query.message.chat,
            from_user=callback_query.from_user,
            text="/settings"
        )
        await cmd_settings(temp_message)

# Button handlers
@dp.message_handler(text="🔍 Find Partner", state=Form.ready)
async def search_partner(message: types.Message):
    await search_for_partner(message.from_user.id, message)

@dp.message_handler(text="❌ Cancel Search", state=Form.ready)
async def cancel_search(message: types.Message):
    user_id = message.from_user.id
    if user_id in waiting_users:
        waiting_users.pop(user_id)
        await message.answer("Search canceled.", reply_markup=main_menu_kb)
    else:
        await message.answer("You weren't searching.", reply_markup=main_menu_kb)

@dp.message_handler(text="❌ End Chat", state=Form.ready)
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    partner_id = chat_pairs.pop(user_id, None)
    
    if partner_id:
        chat_pairs.pop(partner_id, None)
        await bot.send_message(partner_id, "⚠️ Chat ended.", reply_markup=main_menu_kb)
    
    await message.answer("✅ Chat ended.", reply_markup=main_menu_kb)

@dp.message_handler(text="⚙️ Settings", state=Form.ready)
async def settings_button(message: types.Message):
    await cmd_settings(message)

@dp.message_handler(text="ℹ️ Help", state='*')
async def show_help(message: types.Message):
    await cmd_help(message)

# Message handler
@dp.message_handler(state=Form.ready, content_types=types.ContentType.ANY)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in chat_pairs:
        if message.text not in ["🔍 Find Partner", "❌ End Chat", "ℹ️ Help", "❌ Cancel Search", "⚙️ Settings"]:
            await message.answer("Press 🔍 Find Partner to start chatting!", reply_markup=main_menu_kb)
        return
    
    partner_id = chat_pairs[user_id]
    
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
        logger.error(f"Error forwarding message: {e}")
        chat_pairs.pop(user_id, None)
        chat_pairs.pop(partner_id, None)
        await message.answer("⚠️ Partner disconnected.", reply_markup=main_menu_kb)

if __name__ == '__main__':
    logger.info("Starting bot...")
    executor.start_polling(dp, skip_updates=True)