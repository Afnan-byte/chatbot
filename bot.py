from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import BOT_TOKEN
import logging
import random
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Define conversation states
class Form(StatesGroup):
    waiting_for_gender = State()
    ready = State()

# Track users and chat pairs
waiting_users = {}  # user_id: {"gender": str, "name": str, "preferred_gender": str}
chat_pairs = {}     # user_id: partner_id

# Welcome messages
WELCOME_MESSAGES = [
    "🌟 Welcome to MalluConnect! Let's find you a great chat partner.",
    "🌴 Hello Malayali! Ready to meet someone new?",
    "👋 Welcome! Your next interesting conversation starts here.",
    "💬 Hi there! Let's connect you with someone special."
]

# Connection messages
CONNECTION_MESSAGES = [
    "You've been connected with {gender}! Start with a hello 👋",
    "Found someone for you! They're {gender}. Break the ice!",
    "Match made! Your partner is {gender}. Say hi! 😊",
    "Connection successful! Your chat partner is {gender}."
]

# Inline keyboard for gender selection
def get_gender_keyboard(current_gender=""):
    current_gender = current_gender.lower()
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = [
        types.InlineKeyboardButton(
            "👨 Male" + (" ✅" if current_gender == "male" else ""),
            callback_data="gender_male"
        ),
        types.InlineKeyboardButton(
            "👩 Female" + (" ✅" if current_gender == "female" else ""),
            callback_data="gender_female"
        ),
        types.InlineKeyboardButton(
            "🧑 Other" + (" ✅" if current_gender not in ["male", "female"] else ""),
            callback_data="gender_other"
        )
    ]
    kb.add(*buttons)
    return kb

# Inline keyboard for preferred gender selection
preferred_gender_kb = types.InlineKeyboardMarkup(row_width=3)
preferred_gender_kb.add(
    types.InlineKeyboardButton("👨 Males", callback_data="pref_male"),
    types.InlineKeyboardButton("👩 Females", callback_data="pref_female"),
    types.InlineKeyboardButton("🧑 Anyone", callback_data="pref_any")
)

# Main menu keyboard
main_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
main_menu_kb.row(types.KeyboardButton("🔍 Find Partner"))
main_menu_kb.row(types.KeyboardButton("❌ End Chat"), types.KeyboardButton("ℹ️ Help"))

# Searching menu keyboard
searching_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
searching_menu_kb.row(types.KeyboardButton("❌ Cancel Search"))
searching_menu_kb.row(types.KeyboardButton("ℹ️ Help"))

# Help message
HELP_TEXT = """
<b>🤝 MalluConnect Help</b>

<u>📌 How to Use:</u>
1. Set your gender when you start
2. Use <b>🔍 Find Partner</b> to connect with someone
3. Chat anonymously until you or your partner ends the chat
4. Use <b>❌ End Chat</b> anytime to disconnect

<u>✨ Features:</u>
- 100% anonymous chatting
- Gender preferences available
- Text, stickers, photos & videos supported
- Safe and respectful environment

<u>🔧 Commands:</u>
/start - Restart the bot
/help - Show this help message
/settings - Change your preferences

<u>🚫 Rules:</u>
- No harassment or inappropriate content
- Respect all users
- No spam or advertisements

<i>⚠️ Violating rules may result in a ban.</i>
"""

async def search_for_partner(user_id: int, message: types.Message = None):
    if user_id in chat_pairs:
        if message:
            await message.answer("⚠️ You're already in a chat. Please end it first to find a new partner.", 
                               reply_markup=main_menu_kb)
        return

    user_data = waiting_users.get(user_id, {})
    user_gender = user_data.get("gender", "Unknown")
    user_pref = user_data.get("preferred_gender", "any")

    # Search for available partner with preferences
    partner_id = None
    for uid, partner_data in list(waiting_users.items()):
        if (uid != user_id and 
            uid not in chat_pairs and 
            (user_pref == "any" or partner_data.get("gender", "").lower() in user_pref) and
            (partner_data.get("preferred_gender", "any") == "any" or 
             user_gender.lower() in partner_data.get("preferred_gender", "any"))):
            partner_id = uid
            break

    if partner_id:
        # Match found
        chat_pairs[user_id] = partner_id
        chat_pairs[partner_id] = user_id

        user_data = waiting_users.pop(user_id)
        partner_data = waiting_users.pop(partner_id)

        # Send welcome messages
        connection_msg = random.choice(CONNECTION_MESSAGES).format(gender=partner_data['gender'])
        await bot.send_message(
            user_id,
            f"🎉 {connection_msg}\n\n<b>Remember:</b>\n- Be respectful\n- Keep it friendly\n- Have fun!",
            reply_markup=main_menu_kb
        )
        
        partner_connection_msg = random.choice(CONNECTION_MESSAGES).format(gender=user_data['gender'])
        await bot.send_message(
            partner_id,
            f"🎉 {partner_connection_msg}\n\n<b>Remember:</b>\n- Be respectful\n- Keep it friendly\n- Have fun!",
            reply_markup=main_menu_kb
        )
    else:
        if message:
            wait_time = random.randint(1, 5)
            await message.answer(
                f"🔍 Searching for a partner...\n\n"
                f"⏳ Estimated wait time: {wait_time} minute(s)\n"
                f"💡 Tip: You can cancel anytime if you change your mind",
                reply_markup=searching_menu_kb
            )
        if user_id not in waiting_users:
            chat = await bot.get_chat(user_id)
            waiting_users[user_id] = {
                "gender": waiting_users.get(user_id, {}).get("gender", "Unknown"),
                "preferred_gender": waiting_users.get(user_id, {}).get("preferred_gender", "any"),
                "name": chat.full_name
            }

@dp.message_handler(commands=['start', 'restart'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    chat = await bot.get_chat(user_id)

    # Clear any existing connections
    if user_id in chat_pairs:
        partner_id = chat_pairs[user_id]
        chat_pairs.pop(user_id, None)
        chat_pairs.pop(partner_id, None)
        await bot.send_message(partner_id, "⚠️ Your partner has disconnected.", reply_markup=main_menu_kb)

    welcome_text = random.choice(WELCOME_MESSAGES)
    await Form.waiting_for_gender.set()
    
    await message.answer(welcome_text, reply_markup=types.ReplyKeyboardRemove())
    await message.answer("First, please select your gender:", reply_markup=get_gender_keyboard())

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb)

@dp.message_handler(commands=['settings'])
async def cmd_settings(message: types.Message):
    user_id = message.from_user.id
    if user_id not in waiting_users and user_id not in chat_pairs:
        await message.answer("Please use /start first to set up your profile.")
        return
    
    settings_kb = types.InlineKeyboardMarkup(row_width=2)
    settings_kb.add(
        types.InlineKeyboardButton("Change Gender", callback_data="change_gender"),
        types.InlineKeyboardButton("Change Preferences", callback_data="change_pref")
    )
    
    current_gender = waiting_users.get(user_id, {}).get("gender", "Not set")
    current_pref = waiting_users.get(user_id, {}).get("preferred_gender", "any").capitalize()
    
    await message.answer(
        f"⚙️ <b>Your Current Settings</b>\n\n"
        f"👤 Gender: {current_gender}\n"
        f"💞 Preferred Partners: {current_pref}\n\n"
        f"What would you like to change?",
        reply_markup=settings_kb
    )

@dp.callback_query_handler(lambda c: c.data == "change_gender", state='*')
async def change_gender(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    current_gender = waiting_users.get(user_id, {}).get("gender", "").lower()
    
    await bot.send_message(
        callback_query.from_user.id,
        "Select your gender:",
        reply_markup=get_gender_keyboard(current_gender)
    )

@dp.callback_query_handler(lambda c: c.data.startswith("gender_"), state='*')
async def process_gender(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    gender_map = {
        "gender_male": "👨 Male",
        "gender_female": "👩 Female",
        "gender_other": "🧑 Other"
    }
    gender = gender_map.get(callback_query.data, "🧑 Other")

    if user_id in waiting_users:
        waiting_users[user_id]["gender"] = gender
    else:
        chat = await bot.get_chat(user_id)
        waiting_users[user_id] = {
            "gender": gender,
            "preferred_gender": "any",
            "name": chat.full_name
        }

    await bot.answer_callback_query(callback_query.id, f"Gender set to {gender}")
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"✅ <b>Gender updated to:</b> {gender}",
            reply_markup=None
        )
    except:
        pass

    # If in initial setup, proceed to preferences
    if await state.get_state() == Form.waiting_for_gender.state:
        await bot.send_message(
            callback_query.from_user.id,
            "Now, who would you like to chat with?",
            reply_markup=preferred_gender_kb
        )
    else:
        # Return to settings after change
        await cmd_settings(types.Message(
            chat=callback_query.message.chat,
            from_user=callback_query.from_user,
            text="/settings"
        ))

@dp.callback_query_handler(lambda c: c.data == "change_pref", state='*')
async def change_pref(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "Who would you like to chat with?",
        reply_markup=preferred_gender_kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("pref_"), state='*')
async def process_preferred_gender(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    pref_map = {
        "pref_male": ("👨 Males", "male"),
        "pref_female": ("👩 Females", "female"),
        "pref_any": ("🧑 Anyone", "any")
    }
    pref_text, pref_value = pref_map.get(callback_query.data, ("🧑 Anyone", "any"))

    if user_id in waiting_users:
        waiting_users[user_id]["preferred_gender"] = pref_value
    else:
        chat = await bot.get_chat(user_id)
        waiting_users[user_id] = {
            "gender": "Unknown",
            "preferred_gender": pref_value,
            "name": chat.full_name
        }

    await bot.answer_callback_query(callback_query.id, f"Preferences set to {pref_text}")
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"✅ <b>Preferences updated to:</b> {pref_text}",
            reply_markup=None
        )
    except:
        pass

    if await state.get_state() == Form.waiting_for_gender.state:
        await Form.ready.set()
        await bot.send_message(
            callback_query.from_user.id,
            f"🌟 Setup complete!\n\n"
            f"<b>Your gender:</b> {waiting_users[user_id].get('gender', 'Not set')}\n"
            f"<b>Looking for:</b> {pref_text}\n\n"
            f"Press <b>🔍 Find Partner</b> when you're ready!",
            reply_markup=main_menu_kb
        )
    else:
        await cmd_settings(types.Message(
            chat=callback_query.message.chat,
            from_user=callback_query.from_user,
            text="/settings"
        ))

@dp.message_handler(text="🔍 Find Partner", state=Form.ready)
async def search_partner(message: types.Message):
    user_id = message.from_user.id
    if user_id in chat_pairs:
        await message.answer("⚠️ You're already in a chat. Please end it first to find a new partner.", 
                           reply_markup=main_menu_kb)
        return
    
    await message.answer("Starting your search... 🌟", reply_markup=searching_menu_kb)
    await search_for_partner(user_id, message)

@dp.message_handler(text="❌ Cancel Search", state=Form.ready)
async def cancel_search(message: types.Message):
    user_id = message.from_user.id
    if user_id in waiting_users:
        waiting_users.pop(user_id)
        await message.answer("🔍 Search canceled. You can try again whenever you're ready.", 
                           reply_markup=main_menu_kb)
    else:
        await message.answer("You weren't searching for a partner.", reply_markup=main_menu_kb)

@dp.message_handler(text="❌ End Chat", state=Form.ready)
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    partner_id = chat_pairs.pop(user_id, None)

    if partner_id:
        chat_pairs.pop(partner_id, None)
        await bot.send_message(
            partner_id,
            "⚠️ Your partner has ended the chat.\n\n"
            "We hope you had a good conversation! Use 🔍 Find Partner to connect with someone new.",
            reply_markup=main_menu_kb
        )
        await message.answer(
            "✅ Chat ended successfully.\n\n"
            "Thank you for being respectful! Use 🔍 Find Partner whenever you want to chat again.",
            reply_markup=main_menu_kb
        )
    else:
        await message.answer("You're not currently in a chat.", reply_markup=main_menu_kb)

@dp.message_handler(text="ℹ️ Help", state='*')
async def show_help(message: types.Message):
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb)

@dp.message_handler(state=Form.ready, content_types=types.ContentType.ANY)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    if user_id not in chat_pairs:
        if message.text not in ["🔍 Find Partner", "❌ End Chat", "ℹ️ Help", "❌ Cancel Search"]:
            await message.answer("💡 You're not connected to anyone yet. Press 🔍 Find Partner to start chatting!")
        return

    partner_id = chat_pairs[user_id]

    try:
        if message.text:
            await bot.send_message(partner_id, message.text)
        elif message.sticker:
            await bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.photo:
            await bot.send_photo(partner_id, message.photo[-1].file_id, 
                                caption=message.caption if message.caption else "")
        elif message.video:
            await bot.send_video(partner_id, message.video.file_id, 
                               caption=message.caption if message.caption else "")
        elif message.voice:
            await bot.send_voice(partner_id, message.voice.file_id)
        else:
            await message.reply("⚠️ This message type isn't supported yet. Try text, photos, videos, or stickers.")
    except Exception as e:
        logger.error(f"Error forwarding message: {e}")
        await message.answer("⚠️ Couldn't deliver your message. Your partner might have left the chat.")
        
        # Clean up the connection
        chat_pairs.pop(user_id, None)
        chat_pairs.pop(partner_id, None)
        
        await message.answer("You've been disconnected. Press 🔍 Find Partner to chat with someone new.",
                           reply_markup=main_menu_kb)

if __name__ == '__main__':
    logger.info("Starting MalluConnect bot...")
    executor.start_polling(dp, skip_updates=True)