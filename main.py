import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import BOT_TOKEN, ADMIN_ID, CHANNELS, REFERRAL_REWARD, MIN_WITHDRAW, TIKTOK_REWARD
from database import init_db, add_user, get_user, update_balance, increment_referrals

logging.basicConfig(level=logging.INFO)

# 1. FastAPI ዌብ ሰርቨር (Render እንዳይተኛ)
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "running", "bot": "Ethio Kefay Rewards Bot is active!"}

# 2. የቴሌግራም ቦት
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- 1. የቁልፍ ሰሌዳዎች (Keyboards) ማዘጋጃ ---

# የቻናል መጋበዣ ቁልፍ (Force Join Keyboard)
def get_join_keyboard():
    builder = InlineKeyboardBuilder()
    for index, channel in enumerate(CHANNELS, start=1):
        # ቻናሎቹ @ ካላቸው ወደ t.me ሊንክ እንቀይራቸዋለን
        clean_channel = channel.replace("@", "")
        builder.row(types.InlineKeyboardButton(
            text=f"📢 ቻናል {index}-ን ተቀላቀል", 
            url=f"https://t.me/{clean_channel}"
        ))
    builder.row(types.InlineKeyboardButton(text="✅ ተቀላቅያለሁ (Check)", callback_data="check_membership"))
    return builder.as_markup()

# የቦቱ ዋና ሜኑ ቁልፎች (Main Menu Keyboard)
def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="👤 Profile (የእኔ መረጃ)"),
        types.KeyboardButton(text="💰 Balance (ቀሪ ሂሳብ)")
    )
    builder.row(
        types.KeyboardButton(text="🔗 My Referral Link"),
        types.KeyboardButton(text="🎵 TikTok Tasks")
    )
    builder.row(
        types.KeyboardButton(text="💸 Withdraw (ብር ማውጫ)"),
        types.KeyboardButton(text="ℹ️ Help (እርዳታ)")
    )
    return builder.as_markup(resize_keyboard=True)

# --- 2. የቻናል አባልነት ማረጋገጫ (Force Join Checker) ---
async def check_user_joined_all(user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logging.error(f"ቻናል ማረጋገጥ አልተቻለም {channel}: {e}")
            # ቦቱ በቻናሉ ላይ አድሚን ካልተደረገ ስህተት ሊሰጥ ይችላል፤ ለጊዜው እንዲያልፍ True እናደርጋለን
            return True 
    return True

# --- 3. የቦቱ ዋና ትዕዛዞች ---

WELCOME_TEXT = (
    "🎉 እንኳን ወደ Ethio Kefay Rewards Bot በደህና መጡ!\n\n"
    "👥 ጓደኞችዎን ይጋብዙ እና 3 ETB በእያንዳንዱ ትክክለኛ Referral ያግኙ።\n"
    "🎵 TikTok Task በማጠናቀቅ ተጨማሪ 3 ETB ያግኙ።\n\n"
    "💸 100 ETB ሲደርሱ በ Telebirr, CBE ወይም M-PESA Ethiopia ገንዘብዎን ማውጣት ይችላሉ።"
)

@dp.message(CommandStart())
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "No_Username"
    
    # ሪፈራል መኖሩን ማረጋገጥ
    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].isdigit():
        referred_by = int(args[1])
        if referred_by == user_id:
            referred_by = None

    # ተጠቃሚውን በዳታቤዝ መመዝገብ
    is_new = await add_user(user_id, username, referred_by)
    
    # የቻናል አባልነቱን ማረጋገጥ
    is_member = await check_user_joined_all(user_id)
    if not is_member:
        await message.answer(
            "❌ ይቅርታ! ቦቱን ለመጠቀም መጀመሪያ ከታች ያሉትን ቻናሎች መቀላቀል አለብዎት።\n"
            "ሁሉንም ቻናሎች ከተቀላቀሉ በኋላ '✅ ተቀላቅያለሁ (Check)' የሚለውን ይጫኑ።",
            reply_markup=get_join_keyboard()
        )
        return

    # አዲስ ተጠቃሚ ከሆነ እና በሌላ ሰው ከተጋበዘ ለጋባዡ 3 ETB መክፈል
    if is_new and referred_by:
        await update_balance(referred_by, REFERRAL_REWARD)
        await increment_referrals(referred_by)
        try:
            await bot.send_message(
                chat_id=referred_by,
                text=f"👥 አዲስ ሰው በሊንክዎ ገብቷል!\n🎁 +{REFERRAL_REWARD} ETB ወደ አካውንትዎ ተጨምሯል።"
            )
        except Exception:
            pass

    await message.answer(WELCOME_TEXT, reply_markup=get_main_menu())

# 'Check' የሚለውን ኢንላይን በተን ሲጫን ማረጋገጫ
@dp.callback_query(F.data == "check_membership")
async def check_membership_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_member = await check_user_joined_all(user_id)
    
    if is_member:
        await callback.message.delete()
        await callback.message.answer(
            "🎉 እንኳን ደስ አለዎት! ቻናሎቹን በተሳካ ሁኔታ ተቀላቅለዋል።\nአሁን ቦቱን መጠቀም ይችላሉ።",
            reply_markup=get_main_menu()
        )
    else:
        await callback.answer("❌ ሁሉንም ቻናሎች አልተቀላቀሉም! እባክዎ መጀመሪያ ይቀላቀሉ።", show_alert=True)

# 👤 Profile (የእኔ መረጃ)
@dp.message(F.text == "👤 Profile (የእኔ መረጃ)")
async def profile_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        return
    
    profile_text = (
        "👤 **የተጠቃሚ መረጃ**\n\n"
        "🆔 ID: `{user_id}`\n"
        "👤 ስም: @{username}\n"
        "💰 ቀሪ ሂሳብ: {balance} ETB\n"
        "👥 የጋበዟቸው ሰዎች: {referrals} ሰው\n"
    ).format(
        user_id=user['user_id'],
        username=user['username'],
        balance=user['balance'],
        referrals=user['referrals']
    )
    await message.answer(profile_text, parse_mode="Markdown")

# 💰 Balance (ቀሪ ሂሳብ)
@dp.message(F.text == "💰 Balance (ቀሪ ሂሳብ)")
async def balance_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        return
    await message.answer(f"💰 የእርስዎ ቀሪ ሂሳብ፦ **{user['balance']} ETB** ነው ።", parse_mode="Markdown")

# 🔗 My Referral Link
@dp.message(F.text == "🔗 My Referral Link")
async def referral_handler(message: types.Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    ref_text = (
        "🔗 **የእርስዎ መጋበዣ ሊንክ (Referral Link)**\n\n"
        "ይህን ሊንክ ለጓደኞችዎ ያጋሩ፤ እያንዳንዱ በእርስዎ ሊንክ የሚመዘገብ ሰው **3.0 ETB** ያስገኝልዎታል! 🎉\n\n"
        f"👉 `{ref_link}`"
    )
    await message.answer(ref_text, parse_mode="Markdown")

# ℹ️ Help (እርዳታ)
@dp.message(F.text == "ℹ️ Help (እርዳታ)")
async def help_handler(message: types.Message):
    help_text = (
        "ℹ️ **ስለ Ethio Kefay Rewards Bot**\n\n"
        "1️⃣ **እንዴት ብር ማግኘት እችላለሁ?**\n"
        "• የእርስዎን መጋበዣ ሊንክ በመጠቀም ጓደኞችዎን ሲጋብዙ እያንዳንዱ ሰው 3 ETB ያስገኝልዎታል።\n"
        "• የቲክቶክ ተግባር (Task) በመስራት ተጨማሪ ብር ያገኛሉ።\n\n"
        "2️⃣ **ዝቅተኛው የማውጫ መጠን ስንት ነው?**\n"
        f"• ዝቅተኛው የማውጫ መጠን **{MIN_WITHDRAW} ETB** ነው።\n\n"
        "3️⃣ **ክፍያ እንዴት እቀበላለሁ?**\n"
        "• በTelebirr, CBE (የኢትዮጵያ ንግድ ባንክ) ወይም M-PESA ማውጣት ይችላሉ።"
    )
    await message.answer(help_text, parse_mode="Markdown")

async def run_bot():
    await init_db()
    await dp.start_polling(bot)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
