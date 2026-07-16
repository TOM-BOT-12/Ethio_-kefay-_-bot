import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import aiosqlite

from config import BOT_TOKEN, ADMIN_ID, CHANNELS, REFERRAL_REWARD, MIN_WITHDRAW, TIKTOK_REWARD
from database import init_db, add_user, get_user, update_balance, increment_referrals, DB_PATH

logging.basicConfig(level=logging.INFO)

# 1. FastAPI ዌብ ሰርቨር (Render እንዳይተኛ)
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "running", "bot": "Ethio Kefay Rewards Bot is active!"}

# 2. የቴሌግራም ቦት
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- FSM (የተጠቃሚዎችን ምልልስ ለመቆጣጠር) ---
class UserStates(StatesGroup):
    waiting_for_withdraw_method = State()
    waiting_for_account_info = State()
    waiting_for_tiktok_screenshot = State()
    waiting_for_broadcast_msg = State()

# --- የቁልፍ ሰሌዳዎች (Keyboards) ---

# የቻናል መጋበዣ ቁልፍ (Force Join Keyboard)
def get_join_keyboard():
    builder = InlineKeyboardBuilder()
    for index, channel in enumerate(CHANNELS, start=1):
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

# የመክፈያ ዘዴዎች መምረጫ ቁልፍ
def get_payment_methods():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📱 Telebirr", callback_data="pay_telebirr"))
    builder.row(types.InlineKeyboardButton(text="🏦 CBE (የንግድ ባንክ)", callback_data="pay_cbe"))
    builder.row(types.InlineKeyboardButton(text="📱 M-PESA Ethiopia", callback_data="pay_mpesa"))
    return builder.as_markup()

# --- የቻናል አባልነት ማረጋገጫ ---
async def check_user_joined_all(user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            # ቦቱ አድሚን ካልሆነ እንዳይስተጓጎል True እናደርጋለን
            return True 
    return True

# --- የቦቱ ዋና ትዕዛዞች ---

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
    
    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].isdigit():
        referred_by = int(args[1])
        if referred_by == user_id:
            referred_by = None

    is_new = await add_user(user_id, username, referred_by)
    is_member = await check_user_joined_all(user_id)
    
    if not is_member:
        await message.answer(
            "❌ ይቅርታ! ቦቱን ለመጠቀም መጀመሪያ ከታች ያሉትን ቻናሎች መቀላቀል አለብዎት።\n"
            "ሁሉንም ቻናሎች ከተቀላቀሉ በኋላ '✅ ተቀላቅያለሁ (Check)' የሚለውን ይጫኑ።",
            reply_markup=get_join_keyboard()
        )
        return

    # አዲስ ተጠቃሚ ከሆነና ከተጋበዘ
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

# 👤 Profile
@dp.message(F.text == "👤 Profile (የእኔ መረጃ)")
async def profile_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user: return
    profile_text = (
        "👤 **የተጠቃሚ መረጃ**\n\n"
        "🆔 ID: `{user_id}`\n"
        "👤 ስም: @{username}\n"
        "💰 ቀሪ ሂሳብ: {balance} ETB\n"
        "👥 የጋበዟቸው ሰዎች: {referrals} ሰው\n"
    ).format(user_id=user['user_id'], username=user['username'], balance=user['balance'], referrals=user['referrals'])
    await message.answer(profile_text, parse_mode="Markdown")

# 💰 Balance
@dp.message(F.text == "💰 Balance (ቀሪ ሂሳብ)")
async def balance_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user: return
    await message.answer(f"💰 የእርስዎ ቀሪ ሂሳብ፦ **{user['balance']} ETB** ነው ።", parse_mode="Markdown")

# 🔗 Referral Link
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

# ℹ️ Help
@dp.message(F.text == "ℹ️ Help (እርዳታ)")
async def help_handler(message: types.Message):
    help_text = (
        "ℹ️ **ስለ Ethio Kefay Rewards Bot**\n\n"
        "1️⃣ **እንዴት ብር ማግኘት እችላለሁ?**\n"
        "• መጋበዣ ሊንክዎን ለሰዎች በመላክና ጓደኞችዎን በመጋበዝ።\n"
        "• የቲክቶክ ተግባር (Task) በመስራት ተጨማሪ ብር ያገኛሉ።\n\n"
        "2️⃣ **ዝቅተኛው የማውጫ መጠን ስንት ነው?**\n"
        f"• ዝቅተኛው የማውጫ መጠን **{MIN_WITHDRAW} ETB** ነው።"
    )
    await message.answer(help_text, parse_mode="Markdown")

# --- 💸 WITHDRAW SYSTEM (የብር ማውጫ ክፍል) ---
@dp.message(F.text == "💸 Withdraw (ብር ማውጫ)")
async def withdraw_handler(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user: return
    
    if user['balance'] < MIN_WITHDRAW:
        await message.answer(f"❌ ይቅርታ! ማውጣት የሚችሉት ዝቅተኛው የገንዘብ መጠን **{MIN_WITHDRAW} ETB** ነው።\nየእርስዎ የአሁኑ ሂሳብ፦ **{user['balance']} ETB** ነው።")
        return
        
    await message.answer("💸 እባክዎ የክፍያ መቀበያ ዘዴዎን ይምረጡ፦", reply_markup=get_payment_methods())
    await state.set_state(UserStates.waiting_for_withdraw_method)

@dp.callback_query(F.data.startswith("pay_"), UserStates.waiting_for_withdraw_method)
async def process_withdraw_method(callback: types.CallbackQuery, state: FSMContext):
    method_map = {
        "pay_telebirr": "Telebirr",
        "pay_cbe": "CBE (ንግድ ባንክ)",
        "pay_mpesa": "M-PESA"
    }
    method = method_map.get(callback.data)
    await state.update_data(withdraw_method=method)
    
    await callback.message.delete()
    await callback.message.answer(f"👉 እባክዎ የ **{method}** ስልክ ቁጥር ወይም የባንክ ሂሳብ ቁጥርዎን እና ሙሉ ስምዎን ያስገቡ፦")
    await state.set_state(UserStates.waiting_for_account_info)

@dp.message(UserStates.waiting_for_account_info)
async def process_account_info(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    account_info = message.text
    user_data = await state.get_data()
    method = user_data.get("withdraw_method")
    
    user = await get_user(user_id)
    amount = user['balance']
    
    # በዳታቤዝ መመዝገብ
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO withdrawals (user_id, amount, method, account) VALUES (?, ?, ?, ?)",
            (user_id, amount, method, account_info)
        )
        # የተጠቃሚውን balance ወደ 0 ማድረግ
        await db.execute("UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,))
        await db.commit()
        
    await message.answer("✅ የብር ማውጫ ጥያቄዎ በተሳካ ሁኔታ ተመዝግቧል! በአድሚን ተገምግሞ በቅርቡ ይከፈልዎታል።")
    
    # ለአድሚን ማሳወቅ
    admin_msg = (
        "💸 **አዲስ የብር ማውጫ ጥያቄ ደርሶዎታል!**\n\n"
        f"👤 ተጠቃሚ ID: `{user_id}`\n"
        f"💰 የገንዘብ መጠን: **{amount} ETB**\n"
        f"📱 የመክፈያ ዘዴ: {method}\n"
        f"💳 አካውንት: `{account_info}`\n\n"
        f"ለማጽደቅ: `/approve {user_id} {amount}` ይላኩ።\n"
        f"ለመሰረዝ: `/reject {user_id} {amount}` ይላኩ።"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
    except Exception:
        pass
        
    await state.clear()

# --- 🎵 TIKTOK TASK SYSTEM (የቲክቶክ ተግባር ክፍል) ---
@dp.message(F.text == "🎵 TikTok Tasks")
async def tiktok_task_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE user_id = ?", (user_id,)) as cursor:
            task = await cursor.fetchone()
            
    if task and task['task_status'] == 'approved':
        await message.answer("✅ ይህንን ተግባር አስቀድመው አጠናቀው 3.0 ETB ተቀብለዋል!")
        return
    elif task and task['task_status'] == 'pending':
        await message.answer("⏳ የላኩት ማረጋገጫ በአድሚን በመገምገም ላይ ነው፤ እባክዎ በትዕግስት ይጠብቁ።")
        return

    task_instruction = (
        "🎵 **የቲክቶክ ፎሎው ተግባር**\n\n"
        "1. ከታች ያለውን ሊንክ ተጭነው የቲክቶክ አካውንታችንን Follow ያድርጉ።\n"
        "🔗 [TikTok ሊንክ እዚህ ይጫኑ](https://www.tiktok.com)\n\n"
        "2. Follow ማድረጎን የሚያሳይ **Screenshot (ፎቶ)** ወደዚህ ቦት ይላኩ።\n\n"
        "⚠️ ማስታወሻ: ሀሰተኛ ፎቶ መላክ ከቦቱ ሙሉ በሙሉ ያሳግዳል!"
    )
    await message.answer(task_instruction, parse_mode="Markdown")
    await state.set_state(UserStates.waiting_for_tiktok_screenshot)

@dp.message(UserStates.waiting_for_tiktok_screenshot, F.photo)
async def process_tiktok_screenshot(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id # ትልቁን ፎቶ መውሰድ
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET task_status = 'pending' WHERE user_id = ?", (user_id,))
        await db.commit()
        
    await message.answer("✅ ማረጋገጫዎ ለአድሚን ተልኳል! ሲረጋገጥ 3.0 ETB ወደ አካውንትዎ ይጨመራል።")
    
    # ለአድሚን ማሳወቅ
    admin_builder = InlineKeyboardBuilder()
    admin_builder.row(
        types.InlineKeyboardButton(text="✅ Approve (ቀበል)", callback_data=f"tsk_app_{user_id}"),
        types.InlineKeyboardButton(text="❌ Reject (ሰርዝ)", callback_data=f"tsk_rej_{user_id}")
    )
    
    try:
        await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=f"🎵 **አዲስ የቲክቶክ ማረጋገጫ!**\n\nተጠቃሚ ID: `{user_id}`\nስም: @{message.from_user.username}\n\nምን ማድረግ ይፈልጋሉ?",
            reply_markup=admin_builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await state.clear()

# --- 👑 ADMIN PANEL (የአድሚን መቆጣጠሪያዎች) ---

@dp.callback_query(F.data.startswith("tsk_app_"))
async def admin_approve_task(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET task_status = 'approved', tiktok_done = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
        
    await update_balance(user_id, TIKTOK_REWARD)
    await callback.message.edit_caption(caption="✅ የቲክቶክ ተግባሩ ጸድቋል! ለተጠቃሚው 3 ETB ተከፍሏል።")
    try:
        await bot.send_message(chat_id=user_id, text=f"🎉 እንኳን ደስ አለዎት! የቲክቶክ ተግባርዎ በአድሚን ጽድቆ **{TIKTOK_REWARD} ETB** ወደ ቀሪ ሂሳብዎ ተጨምሯል።")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("tsk_rej_"))
async def admin_reject_task(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET task_status = 'rejected' WHERE user_id = ?", (user_id,))
        await db.commit()
        
    await callback.message.edit_caption(caption="❌ የቲክቶክ ተግባሩ ውድቅ ተደርጓል።")
    try:
        await bot.send_message(chat_id=user_id, text="❌ ይቅርታ! የላኩት የቲክቶክ ማረጋገጫ ፎቶ ትክክል ባለመሆኑ በአድሚን ውድቅ ተደርጓል።")
    except Exception:
        pass

# አድሚን የብር ማውጫ ለማጽደቅ: /approve USER_ID AMOUNT
@dp.message(Command("approve"))
async def admin_approve_withdraw(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("ቅርጸት፦ `/approve USER_ID AMOUNT`")
        return
    user_id, amount = int(args[1]), float(args[2])
    try:
        await bot.send_message(chat_id=user_id, text=f"🎉 እንኳን ደስ አለዎት! የ **{amount} ETB** የክፍያ ጥያቄዎ በአድሚን ተቀባይነት አግኝቶ ተከፍሎዎታል።")
        await message.answer("✅ ክፍያው መፈጸሙን ለተጠቃሚው አሳውቀናል።")
    except Exception:
        await message.answer("❌ ለተጠቃሚው መልዕክት መላክ አልተቻለም።")

# አድሚን የብር ማውጫ ለመሰረዝ (ገንዘብ ተመላሽ ይደረጋል): /reject USER_ID AMOUNT
@dp.message(Command("reject"))
async def admin_reject_withdraw(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("ቅርጸት፦ `/reject USER_ID AMOUNT`")
        return
    user_id, amount = int(args[1]), float(args[2])
    await update_balance(user_id, amount) # ብሩን እንመልስለታለን
    try:
        await bot.send_message(chat_id=user_id, text=f"❌ ይቅርታ! የ **{amount} ETB** የክፍያ ጥያቄዎ ውድቅ ተደርጓል። ብሩ ወደ አካውንትዎ ተመልሷል።")
        await message.answer("❌ ክፍያው ውድቅ መደረጉን ለተጠቃሚው አሳውቀናል።")
    except Exception:
        await message.answer("❌ ለተጠቃሚው መልዕክት መላክ አልተቻለም።")

# አድሚን ለሁሉም መልዕክት ለመላክ (Broadcast)
@dp.message(Command("broadcast"))
async def admin_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("📢 ለሁሉም ተጠቃሚዎች የሚተላለፈውን መልዕክት ይጻፉ፦")
    await state.set_state(UserStates.waiting_for_broadcast_msg)

@dp.message(UserStates.waiting_for_broadcast_msg)
async def process_broadcast(message: types.Message, state: FSMContext):
    msg_to_send = message.text
    await state.clear()
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
            
    await message.answer(f"⏳ መልዕክቱ ለ {len(users)} ተጠቃሚዎች እየተላከ ነው...")
    sent_count = 0
    for u in users:
        try:
            await bot.send_message(chat_id=u['user_id'], text=msg_to_send)
            sent_count += 1
            await asyncio.sleep(0.05) # ቴሌግራም እንዳያግደን ፍጥነቱን እንቀንሳለን
        except Exception:
            pass
    await message.answer(f"📢 መልዕክቱ በተሳካ ሁኔታ ለ {sent_count} ሰዎች ደርሷል!")

async def run_bot():
    await init_db()
    await dp.start_polling(bot)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
