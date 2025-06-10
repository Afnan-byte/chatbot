from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
import random
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize logging to provide useful output during bot operation
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the Bot and Dispatcher
# parse_mode=types.ParseMode.HTML allows sending messages with HTML formatting
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
# MemoryStorage is used to store states and data in RAM.
# For production, consider using more persistent storage like Redis or a database.
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Define conversation states for the Finite State Machine (FSM)
class Form(StatesGroup):
    waiting_for_gender = State() # State when the bot is waiting for the user to select their gender
    ready = State()              # State when the user has completed initial setup and is ready to chat or search

# Dictionaries to keep track of users and their chat pairs
# waiting_users: Stores user profiles who are currently searching for a partner
# {user_id: {"gender": str, "name": str}}
waiting_users = {}
# chat_pairs: Stores active chat connections between two users
# {user_id: partner_id}
chat_pairs = {}

# Pre-defined welcome messages for a friendly start
WELCOME_MESSAGES = [
    "🌟 Welcome to MalluConnect! Let's find you a great chat partner.",
    "🌴 Hello Malayali! Ready to meet someone new?",
    "👋 Welcome! Your next interesting conversation starts here.",
    "💬 Hi there! Let's connect you with someone special."
]

# Pre-defined connection messages for when a match is found
# {gender} will be replaced with the partner's gender
CONNECTION_MESSAGES = [
    "You've been connected with {gender}! Start with a hello 👋",
    "Found someone for you! They're {gender}. Break the ice!",
    "Match made! Your partner is {gender}. Say hi! 😊",
    "Connection successful! Your chat partner is {gender}."
]

# Function to generate an inline keyboard for gender selection
# current_gender: The user's current gender, used to mark the selected option
def get_gender_keyboard(current_gender=""):
    current_gender = current_gender.lower()
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = [
        types.InlineKeyboardButton(
            "👨 Male" + (" ✅" if current_gender == "👨 male" else ""), # Add tick if male is current
            callback_data="gender_male"
        ),
        types.InlineKeyboardButton(
            "👩 Female" + (" ✅" if current_gender == "👩 female" else ""), # Add tick if female is current
            callback_data="gender_female"
        ),
        types.InlineKeyboardButton(
            "🧑 Other" + (" ✅" if current_gender == "🧑 other" else ""), # Add tick if other is current
            callback_data="gender_other"
        )
    ]
    kb.add(*buttons)
    return kb

# Reply keyboard for the main menu
main_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
main_menu_kb.row(types.KeyboardButton("🔍 Find Partner"))
main_menu_kb.row(types.KeyboardButton("⚙️ Settings"), types.KeyboardButton("ℹ️ Help"))

# Reply keyboard for when the bot is searching for a partner
searching_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
searching_menu_kb.row(types.KeyboardButton("❌ Cancel Search"))
searching_menu_kb.row(types.KeyboardButton("ℹ️ Help"))

# Reply keyboard for when two users are actively chatting
chatting_menu_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
chatting_menu_kb.row(types.KeyboardButton("❌ End Chat"))
chatting_menu_kb.row(types.KeyboardButton("ℹ️ Help"))

# Help message text, formatted with HTML for better presentation
HELP_TEXT = """
<b>🤝 MalluConnect Help</b>

<u>📌 How to Use:</u>
1. Press /start to begin
2. Select your gender
3. Use <b>🔍 Find Partner</b> to connect with someone
4. Chat anonymously until you or your partner ends the chat
5. Use <b>❌ End Chat</b> anytime to disconnect

<u>✨ Features:</u>
- 100% anonymous chatting
- Text, stickers, photos & videos supported
- Safe and respectful environment

<u>🔧 Commands:</u>
/start - Start or restart the bot
/help - Show this help message
/settings - Change your gender

<u>🚫 Rules:</u>
- No harassment or inappropriate content
- Respect all users
- No spam or advertisements

<i>⚠️ Violating rules may result in a ban.</i>
"""

# Asynchronous function to search for a chat partner
async def search_for_partner(user_id: int, message: types.Message = None):
    # Check if the user is already in a chat
    if user_id in chat_pairs:
        if message:
            await message.answer("⚠️ You're already in a chat. Please end it first to find a new partner.",
                                 reply_markup=chatting_menu_kb)
        return

    # Get the current user's data
    user_data = waiting_users.get(user_id, {})
    user_gender = user_data.get("gender", "Unknown").lower()

    partner_id = None
    # Iterate through waiting users to find a suitable match
    # Use list() to create a copy for safe iteration while modifying waiting_users
    for uid, partner_data in list(waiting_users.items()):
        if uid == user_id or uid in chat_pairs:
            continue # Skip self or already chatting partners

        # No preferred gender filter, so any available user is a match
        partner_id = uid
        break

    if partner_id:
        # Match found: establish chat pair
        chat_pairs[user_id] = partner_id
        chat_pairs[partner_id] = user_id

        # Remove both users from the waiting list
        user_data_matched = waiting_users.pop(user_id, None)
        partner_data_matched = waiting_users.pop(partner_id, None)

        # Ensure we have data for both users, otherwise, fall back to "Unknown"
        user_gender_display = user_data_matched.get('gender', 'Unknown') if user_data_matched else 'Unknown'
        partner_gender_display = partner_data_matched.get('gender', 'Unknown') if partner_data_matched else 'Unknown'

        # Send connection messages to both users
        connection_msg_user = random.choice(CONNECTION_MESSAGES).format(gender=partner_gender_display)
        await bot.send_message(
            user_id,
            f"🎉 {connection_msg_user}\n\n<b>Remember:</b>\n- Be respectful\n- Keep it friendly\n- Have fun!",
            reply_markup=chatting_menu_kb
        )

        connection_msg_partner = random.choice(CONNECTION_MESSAGES).format(gender=user_gender_display)
        await bot.send_message(
            partner_id,
            f"🎉 {connection_msg_partner}\n\n<b>Remember:</b>\n- Be respectful\n- Keep it friendly\n- Have fun!",
            reply_markup=chatting_menu_kb
        )
    else:
        # No partner found: inform the user and add them to the waiting list if not already there
        if message:
            wait_time = random.randint(1, 5) # Simulate a random wait time
            await message.answer(
                f"🔍 Searching for a partner...\n\n"
                f"⏳ Estimated wait time: {wait_time} minute(s)\n"
                f"💡 Tip: You can cancel anytime if you change your mind",
                reply_markup=searching_menu_kb
            )
        # Add user to waiting_users if they are not already there
        if user_id not in waiting_users:
            chat = await bot.get_chat(user_id)
            waiting_users[user_id] = {
                "gender": user_data.get("gender", "Unknown"), # Use existing data or default
                "name": chat.full_name
            }

# Handler for the /start and /restart commands
@dp.message_handler(commands=['start', 'restart'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    chat = await bot.get_chat(user_id) # Get chat information for user's full name

    # Clear any existing connections if the user was in a chat
    if user_id in chat_pairs:
        partner_id = chat_pairs.pop(user_id, None) # Remove user from chat_pairs
        if partner_id:
            chat_pairs.pop(partner_id, None) # Remove partner from chat_pairs
            # Inform the partner that the chat has ended
            await bot.send_message(partner_id, "⚠️ Your partner has disconnected.", reply_markup=main_menu_kb)

    # Reset the user's state to waiting_for_gender
    await Form.waiting_for_gender.set()

    # Send a random welcome message and remove any current reply keyboard
    welcome_text = random.choice(WELCOME_MESSAGES)
    await message.answer(welcome_text, reply_markup=types.ReplyKeyboardRemove())

    # Prompt the user to select their gender using an inline keyboard
    # Fetch current gender from waiting_users if exists, to pre-select
    current_gender_for_kb = waiting_users.get(user_id, {}).get("gender", "")
    await message.answer("First, please select your gender:", reply_markup=get_gender_keyboard(current_gender_for_kb))

# Handler for the /help command
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    # Determine which reply keyboard to show based on the user's current state (chatting, searching, or main menu)
    current_state = await dp.current_state(user=message.from_user.id).get_state()
    reply_markup = types.ReplyKeyboardRemove() # Default to no keyboard

    if current_state == Form.ready.state:
        if message.from_user.id in chat_pairs:
            reply_markup = chatting_menu_kb
        else:
            reply_markup = main_menu_kb
    
    # Send the help text with the appropriate keyboard
    await message.answer(HELP_TEXT, reply_markup=reply_markup)

# Handler for the /settings command
@dp.message_handler(commands=['settings'])
async def cmd_settings(message: types.Message):
    user_id = message.from_user.id
    # Ensure the user has started the bot at least once
    if user_id not in waiting_users and user_id not in chat_pairs:
        await message.answer("Please use /start first to set up your profile.")
        return
    
    # Retrieve current gender for display
    current_gender = waiting_users.get(user_id, {}).get("gender", "Not set")

    # Send current settings and inline options to change them
    await message.answer(
        f"⚙️ <b>Your Current Settings</b>\n\n"
        f"👤 Gender: {current_gender}\n\n"
        "You can change your gender below:",
        reply_markup=types.InlineKeyboardMarkup().row(
            types.InlineKeyboardButton("Change Gender", callback_data="change_gender")
        )
    )

# Callback query handler for "Change Gender" button
@dp.callback_query_handler(lambda c: c.data == "change_gender", state='*')
async def change_gender(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id) # Acknowledge the callback
    user_id = callback_query.from_user.id
    # Get the user's current gender to pre-select it in the keyboard
    current_gender = waiting_users.get(user_id, {}).get("gender", "").lower()
    
    await bot.send_message(
        callback_query.from_user.id,
        "Select your gender:",
        reply_markup=get_gender_keyboard(current_gender)
    )

# Callback query handler for gender selection (e.g., "gender_male")
@dp.callback_query_handler(lambda c: c.data.startswith("gender_"), state='*')
async def process_gender(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    # Map callback data to display text for gender
    gender_map = {
        "gender_male": "👨 Male",
        "gender_female": "👩 Female",
        "gender_other": "🧑 Other"
    }
    gender_display = gender_map.get(callback_query.data, "🧑 Other") # Get display name

    # Update or create user data in waiting_users
    if user_id in waiting_users:
        waiting_users[user_id]["gender"] = gender_display # Store display name
    else:
        chat = await bot.get_chat(user_id)
        waiting_users[user_id] = {
            "gender": gender_display,
            "name": chat.full_name
        }

    await bot.answer_callback_query(callback_query.id, f"Gender set to {gender_display}")
    
    # Try to edit the message where the inline keyboard was displayed, to confirm selection
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"✅ <b>Gender updated to:</b> {gender_display}",
            reply_markup=None # Remove the inline keyboard after selection
        )
    except Exception as e:
        logger.warning(f"Could not edit message for gender selection: {e}")
        # If editing fails (e.g., message too old), send a new confirmation message
        await bot.send_message(user_id, f"✅ <b>Gender updated to:</b> {gender_display}")

    # If the user was in the initial setup state, set their state to ready and show main menu
    if await state.get_state() == Form.waiting_for_gender.state:
        await Form.ready.set()
        await bot.send_message(
            callback_query.from_user.id,
            f"🌟 Setup complete!\n\n"
            f"<b>Your gender:</b> {waiting_users[user_id].get('gender', 'Not set')}\n\n"
            f"Press <b>🔍 Find Partner</b> when you're ready!",
            reply_markup=main_menu_kb
        )
    else:
        # If changing from settings, return to the settings menu
        # This simulates a message from the user to trigger cmd_settings again
        temp_message = types.Message(
            chat=callback_query.message.chat,
            from_user=callback_query.from_user,
            text="/settings"
        )
        await cmd_settings(temp_message)


# Message handler for "🔍 Find Partner" button when in 'ready' state
@dp.message_handler(text="🔍 Find Partner", state=Form.ready)
async def search_partner(message: types.Message):
    user_id = message.from_user.id
    # Prevent searching if already in a chat
    if user_id in chat_pairs:
        await message.answer("⚠️ You're already in a chat. Please end it first to find a new partner.",
                             reply_markup=chatting_menu_kb)
        return
    
    # Inform user that search is starting and display searching keyboard
    await message.answer("Starting your search... 🌟", reply_markup=searching_menu_kb)
    # Call the asynchronous search function
    await search_for_partner(user_id, message)

# Message handler for "❌ Cancel Search" button when in 'ready' state
@dp.message_handler(text="❌ Cancel Search", state=Form.ready)
async def cancel_search(message: types.Message):
    user_id = message.from_user.id
    # Remove user from waiting_users if they were searching
    if user_id in waiting_users:
        waiting_users.pop(user_id)
        await message.answer("🔍 Search canceled. You can try again whenever you're ready.",
                             reply_markup=main_menu_kb)
    else:
        # Inform user if they weren't actively searching
        await message.answer("You weren't searching for a partner.", reply_markup=main_menu_kb)

# Message handler for "❌ End Chat" button when in 'ready' state
@dp.message_handler(text="❌ End Chat", state=Form.ready)
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    # Remove the current user from chat_pairs, getting their partner's ID
    partner_id = chat_pairs.pop(user_id, None)

    if partner_id:
        # Remove the partner from chat_pairs as well
        chat_pairs.pop(partner_id, None)
        # Inform the partner that the chat has ended
        await bot.send_message(
            partner_id,
            "⚠️ Your partner has ended the chat.\n\n"
            "We hope you had a good conversation! Use 🔍 Find Partner to connect with someone new.",
            reply_markup=main_menu_kb
        )
        # Confirm to the current user that their chat has ended
        await message.answer(
            "✅ Chat ended successfully.\n\n"
            "Thank you for being respectful! Use 🔍 Find Partner whenever you want to chat again.",
            reply_markup=main_menu_kb
        )
    else:
        # Inform user if they were not in a chat
        await message.answer("You're not currently in a chat.", reply_markup=main_menu_kb)

# Message handler for "⚙️ Settings" button when in 'ready' state
@dp.message_handler(text="⚙️ Settings", state=Form.ready)
async def settings_button(message: types.Message):
    # Call the existing /settings command handler
    await cmd_settings(message)

# Message handler for "ℹ️ Help" button (can be used from any state)
@dp.message_handler(text="ℹ️ Help", state='*')
async def show_help(message: types.Message):
    # Determine which reply keyboard to show based on the user's current state
    current_state = await dp.current_state(user=message.from_user.id).get_state()
    reply_markup = types.ReplyKeyboardRemove() # Default to no keyboard

    if current_state == Form.ready.state:
        if message.from_user.id in chat_pairs:
            reply_markup = chatting_menu_kb
        else:
            reply_markup = main_menu_kb
            
    # Send the help text with the determined keyboard
    await message.answer(HELP_TEXT, reply_markup=reply_markup)

# Generic message handler for all content types when in 'ready' state
# This handler forwards messages between paired users
@dp.message_handler(state=Form.ready, content_types=types.ContentType.ANY)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    # If the user is not in a chat, inform them to find a partner
    if user_id not in chat_pairs:
        # Avoid sending this message if the user clicked a main menu button
        if message.text not in ["🔍 Find Partner", "❌ End Chat", "ℹ️ Help", "❌ Cancel Search", "⚙️ Settings"]:
            await message.answer("💡 You're not connected to anyone yet. Press 🔍 Find Partner to start chatting!",
                                 reply_markup=main_menu_kb)
        return

    partner_id = chat_pairs[user_id] # Get the ID of the partnered user

    try:
        # Forward different types of content
        if message.text:
            await bot.send_message(partner_id, message.text)
        elif message.sticker:
            await bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.photo:
            # Send the largest photo available and include caption if present
            await bot.send_photo(partner_id, message.photo[-1].file_id,
                                 caption=message.caption if message.caption else "")
        elif message.video:
            # Send video and include caption if present
            await bot.send_video(partner_id, message.video.file_id,
                                 caption=message.caption if message.caption else "")
        elif message.voice:
            await bot.send_voice(partner_id, message.voice.file_id)
        else:
            # Inform user if the message type is not supported
            await message.reply("⚠️ This message type isn't supported yet. Try text, photos, videos, or stickers.")
    except Exception as e:
        # Log the error and inform the user if message forwarding fails
        logger.error(f"Error forwarding message: {e}")
        await message.answer("⚠️ Couldn't deliver your message. Your partner might have left the chat.")
        
        # Clean up the connection if an error occurs during forwarding
        chat_pairs.pop(user_id, None)
        chat_pairs.pop(partner_id, None)
        
        await message.answer("You've been disconnected. Press 🔍 Find Partner to chat with someone new.",
                             reply_markup=main_menu_kb)

# Main entry point for the bot
if __name__ == '__main__':
    logger.info("Starting MalluConnect bot...")
    # Start polling for updates from Telegram
    # skip_updates=True ensures that old updates (from when the bot was offline) are ignored
    executor.start_polling(dp, skip_updates=True)