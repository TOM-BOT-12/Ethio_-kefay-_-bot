import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database

# Setup Logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Initialize Bot and Dispatcher
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- States for Forms ---
class UserStates(StatesGroup):
    waiting_for_payment_details = State()
    waiting_for_tiktok_screenshot = State()
    waiting_for_broadcast_msg = State()

# --- Keyboards ---
def get_main_menu():
    kb = [
        [KeyboardButton(text="👤 Profile"), KeyboardButton(text="💰 Balance")],
        [KeyboardButton(text="🔗 My Referral Link"), KeyboardButton(text="🎵 TikTok Task")],
        [KeyboardButton(text="💸 Withdraw"), KeyboardButton(text="👥 Referrals")],
        [KeyboardButton(text="ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_menu():
    kb = [
        [KeyboardButton(text="📢 Broadcast Message"), KeyboardButton(text="📊 Bot Statistics")],
        [KeyboardButton(text="🔙 Back to Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- Force Join Check Helper ---
async def check_force_join(user_id: int) -> bool:
    for channel in config.CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            # If the bot is not admin or channel username is wrong
            return False
    return True

async def send_force_join_msg(message: types.Message):
    builder = InlineKeyboardBuilder()
    for i, channel in enumerate(config.CHANNELS, start=1):
        # Convert channel username to link
        clean_channel = channel.replace("@", "")
        builder.button(text=f"📢 Channel {i}", url=f"https://t.me/{clean_channel}")
    
    builder.button(text="✅ I've Joined / አረጋግጥ", callback_data="check_joined")
    builder.adjust(1)
    
    await message.answer(
        "👋 እባክዎ ቦቱን ከመጠቀምዎ በፊት የእኛን ቻናሎች ይቀላቀሉ!\n"
        "Please join our channels before using the bot!",
        reply_markup=builder.as_markup()
    )

# --- Handlers ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    # Extract referral code if present
    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id == user_id:
                referrer_id = None # Can't refer yourself
        except ValueError:
            referrer_id = None

    # Save user if new
    user_exists = await database.get_user(user_id)
    if not user_exists:
        await database.add_user(user_id, username, referrer_id)
        # If successfully referred by someone, credit them after force join verification
    
    is_joined = await check_force_join(user_id)
    if not is_joined:
        await send_force_join_msg(message)
        return

    # If already joined and is a new referral, process reward
    if not user_exists and referrer_id:
        ref_user = await database.get_user(referrer_id)
        if ref_user:
            await database.update_balance(referrer_id, config.REFERRAL_REWARD)
            await database.increment_referrals(referrer_id)
            try:
                await bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎁 አዲስ ተጠቃሚ በሊንክዎ ገብቷል! +{config.REFERRAL_REWARD} ETB ወደ አካውንትዎ ተጨምሯል።"
                )
            except Exception:
                pass

    welcome_text = (
        f"🎉 እንኳን ወደ **Ethio Kefay Rewards Bot** በደህና መጡ!\n\n"
        f"👥 ጓደኞችዎን ይጋብዙ እና **{config.REFERRAL_REWARD} ETB** በእያንዳንዱ ትክክለኛ Referral ያግኙ።\n"
        f"🎵 TikTok Task በማጠናቀቅ ተጨማሪ **{config.TIKTOK_REWARD} ETB** ያግኙ።\n"
        f"💸 **{config.MIN_WITHDRAW} ETB** ሲደርሱ በ **Telebirr, CBE ወይም M-PESA Ethiopia** ገንዘብዎን ማውጣት ይችላሉ።"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.callback_query(F.data == "check_joined")
async def process_check_joined(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_joined = await check_force_join(user_id)
    
    if not is_joined:
        await callback.answer("❌ ሁሉንም ቻናሎች አልተቀላቀሉም! / You haven't joined all channels!", show_alert=True)
        return
    
    await callback.answer("✅ ስኬታማ! / Success!", show_alert=False)
    await callback.message.delete()
    
    # Check if referral reward needs to be paid
    user = await database.get_user(user_id)
    if user and user["referred_by"] and user["referrals"] == 0:
        # Check if referrer has already been rewarded for this user to avoid double claim
        referrer_id = user["referred_by"]
        await database.update_balance(referrer_id, config.REFERRAL_REWARD)
        await database.increment_referrals(referrer_id)
        try:
            await bot.send_message(
                chat_id=referrer_id,
                text=f"🎁 አዲስ ተጠቃሚ ቻናል ይቀላቀላል! +{config.REFERRAL_REWARD} ETB ወደ አካውንትዎ ተጨምሯል።"
            )
        except Exception:
            pass

    await callback.message.answer(
        "🎉 እንኳን በደህና መጡ! አሁን ቦቱን መጠቀም ይችላሉ።",
        reply_markup=get_main_menu()
    )

# --- Menu Handlers ---

@dp.message(F.text == "👤 Profile")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    if not await check_force_join(user_id):
        await send_force_join_msg(message)
        return
        
    user = await database.get_user(user_id)
    profile_text = (
        f"👤 **የእርስዎ ፕሮፋይል (Profile)**\n\n"
        f"🆔 ID: `{user['user_id']}`\n"
        f"💰 Balance: `{user['balance']} ETB`\n"
        f"👥 Total Invites: `{user['referrals']} ሰው`\n"
        f"💳 መክፈያ መንገድ: `{user['payment_method'] or 'ያልተመዘገበ'}`\n"
        f"📌 መክፈያ አድራሻ: `{user['payment_details'] or 'ያልተመዘገበ'}`"
    )
    await message.answer(profile_text, parse_mode="Markdown")

@dp.message(F.text == "💰 Balance")
async def show_balance(message: types.Message):
    user_id = message.from_user.id
    if not await check_force_join(user_id):
        await send_force_join_msg(message)
        return
        
    user = await database.get_user(user_id)
    await message.answer(f"💰 **የአሁኑ ቀሪ ሂሳብዎ (Your Balance):**\n\n💵 **{user['balance']} ETB**")

@dp.message(F.text == "🔗 My Referral Link")
async def show_ref_link(message: types.Message):
    user_id = message.from_user.id
    if not await check_force_join(user_id):
        await send_force_join_msg(message)
        return
        
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    share_text = (
        f"🤝 **ይጋብዙ እና ያግኙ!**\n\n"
        f"ይህንን ሊንክ ለወዳጅ ዘመድዎ በመላክ በእያንዳንዱ ሰው **{config.REFERRAL_REWARD} ETB** ያግኙ።\n\n"
        f"🔗 የእርስዎ መጋበዣ ሊንክ (Referral Link):\n`{ref_link}`"
    )
    await message.answer(share_text, parse_mode="Markdown")

@dp.message(F.text == "👥 Referrals")
async def show_referrals(message: types.Message):
    user_id = message.from_user.id
    user = await database.get_user(user_id)
    await message.answer(f"👥 **የጋበዟቸው ጠቅላላ ተጠቃሚዎች ብዛት:** {user['referrals']} ሰው")

@dp.message(F.text == "ℹ️ Help")
async def show_help(message: types.Message):
    help_text = (
        "ℹ️ **ስለ Ethio Kefay Bot መመሪያ**\n\n"
        "1. **ሰዎችን መጋበዝ**፡ የእርስዎን Referral ሊንክ በመጫን ለጓደኞችዎ ይላኩ። ጓደኞችዎ ቦቱን ሲቀላቀሉ 3 ETB ያገኛሉ።\n"
        "2. **ቲክቶክ ታስክ**፡ ቲክቶካችንን ፎሎው በማድረግ ማስረጃ ፎቶ ይላኩ።\n"
        "3. **ገንዘብ ማውጣት**፡ አካውንትዎ 100 ETB ሲሞላ የክፍያ አማራጭ በመምረጥ መጠየቅ ይችላሉ።\n\n"
        "📞 ማናቸውንም ጥያቄ ካለዎት Admin ማነጋገር ይችላሉ።"
    )
    await message.answer(help_text)

# --- TikTok Task Handler ---
@dp.message(F.text == "🎵 TikTok Task")
async def show_tiktok_task(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await check_force_join(user_id):
        await send_force_join_msg(message)
        return
        
    task_text = (
        "🎵 **የቲክቶክ ታስክ (TikTok Task)**\n\n"
        "1. መጀመሪያ ይህንን የቲክቶክ አካውንት Follow ያድርጉ፡\n"
        "👉 [TikTok Account Link](https://www.tiktok.com/@your_tiktok_username)\n\n"
        "2. Follow ማድረጎን የሚያሳይ **Screenshot** ምስል ወደዚህ ቦት ይላኩ።\n\n"
        "⚠️ Admin ምስሉን አረጋግጦ ሲያጸድቅልዎት **3 ETB** ወደ አካውንትዎ ይጨመራል።"
    )
    await message.answer(task_text, parse_mode="Markdown", disable_web_page_preview=True)
    await state.set_state(UserStates.waiting_for_tiktok_screenshot)

@dp.message(UserStates.waiting_for_tiktok_screenshot, F.photo)
async def process_tiktok_screenshot(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    
    # Save request in db
    await database.submit_tiktok_task(user_id, photo_id)
    await state.clear()
    
    await message.answer("✅ ምስሉ በተሳካ ሁኔታ ተልኳል! Admin ካረጋገጠ በኋላ ክፍያዎ ይለቀቃል።")
    
    # Forward/Notify Admin
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve (3 ETB)", callback_data=f"app_tk_{user_id}_{photo_id[:15]}")
    builder.button(text="❌ Reject", callback_data=f"rej_tk_{user_id}")
    builder.adjust(2)
    
    try:
        await bot.send_photo(
            chat_id=config.ADMIN_ID,
            photo=photo_id,
            caption=f"🎵 **አዲስ የTikTok Task ማረጋገጫ ጥያቄ**\n👤 User ID: `{user_id}`\nUsername: @{message.from_user.username}",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Failed to notify admin about TikTok: {e}")

# --- Withdraw Handler ---
@dp.message(F.text == "💸 Withdraw")
async def start_withdraw(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await check_force_join(user_id):
        await send_force_join_msg(message)
        return
        
    user = await database.get_user(user_id)
    if user['balance'] < config.MIN_WITHDRAW:
        await message.answer(f"❌ ዝቅተኛው የማውጫ መጠን **{config.MIN_WITHDRAW} ETB** ነው።\nየእርስዎ ቀሪ ሂሳብ፡ **{user['balance']} ETB**")
        return
        
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Telebirr", callback_data="w_Telebirr")
    builder.button(text="🏦 CBE (Commercial Bank)", callback_data="w_CBE")
    builder.button(text="📱 M-PESA Ethiopia", callback_data="w_MPESA")
    builder.adjust(1)
    
    await message.answer("የመክፈያ አማራጭ ይምረጡ / Choose Payment Method:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("w_"))
async def process_withdraw_method(callback: types.CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[1]
    await callback.message.delete()
    
    await state.update_data(withdraw_method=method)
    await state.set_state(UserStates.waiting_for_payment_details)
    
    await callback.message.answer(
        f"📌 እባክዎ ለ **{method}** የሚጠቀሙበትን ስልክ ቁጥር ወይም የባንክ አካውንት እና ሙሉ ስም ይጻፉልን፡"
    )

@dp.message(UserStates.waiting_for_payment_details)
async def process_withdraw_details(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    details = message.text
    data = await state.get_data()
    method = data.get("withdraw_method")
    
    user = await database.get_user(user_id)
    amount = user['balance']
    
    if amount < config.MIN_WITHDRAW:
        await message.answer("❌ ይቅርታ፣ ቀሪ ሂሳብዎ ከዝቅተኛው መጠን ያነሰ ነው።")
        await state.clear()
        return
        
    # Process DB
    await database.create_withdraw_request(user_id, amount, method, details)
    await database.update_balance(user_id, -amount) # Deduct balance
    await database.set_payment_info(user_id, method, details)
    
    await state.clear()
    await message.answer("✅ የገንዘብ ማውጫ ጥያቄዎ በተሳካ ሁኔታ ተመዝግቧል። Admin በአጭር ጊዜ ውስጥ ይመረምረዋል።")
    
    # Notify Admin
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve Request", callback_data=f"app_wd_{user_id}_{amount}")
    builder.button(text="❌ Reject & Refund", callback_data=f"rej_wd_{user_id}_{amount}")
    builder.adjust(2)
    
    try:
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=(
                f"💸 **አዲስ የገንዘብ ማውጫ ጥያቄ (New Withdraw Request)**\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"💵 መጠን: **{amount} ETB**\n"
                f"🏦 መክፈያ፡ **{method}**\n"
                f"📌 መረጃ፡ `{details}`"
            ),
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Failed to notify admin about withdraw: {e}")

# --- Admin Callback Verification Handlers ---

@dp.callback_query(F.data.startswith("app_tk_"))
async def approve_tiktok(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    target_user_id = int(parts[2])
    
    await database.update_balance(target_user_id, config.TIKTOK_REWARD)
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ APPROVED (3 ETB CREDITED)")
    try:
        await bot.send_message(target_user_id, f"🎉 እንኳን ደስ አለዎት! የቲክቶክ ተግባርዎ ጸድቆ **{config.TIKTOK_REWARD} ETB** ተጨምሮልዎታል።")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("rej_tk_"))
async def reject_tiktok(callback: types.CallbackQuery):
    target_user_id = int(callback.data.split("_")[2])
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ REJECTED")
    try:
        await bot.send_message(target_user_id, "❌ ይቅርታ፣ የላኩት የቲክቶክ ማስረጃ ውድቅ ተደርጓል። እባክዎ በትክክል ፎሎው ማድረጎን ያረጋግጡ።")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("app_wd_"))
async def approve_withdraw(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    target_user_id = int(parts[2])
    amount = float(parts[3])
    
    await callback.message.edit_text(text=callback.message.text + f"\n\n✅ APPROVED (Paid {amount} ETB)")
    try:
        await bot.send_message(target_user_id, f"🎉 ገንዘብ ማውጣት ጥያቄዎ ጸድቋል! {amount} ETB በተመረጠው አካውንትዎ ተልኳል።")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("rej_wd_"))
async def reject_withdraw(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    target_user_id = int(parts[2])
    amount = float(parts[3])
    
    await database.update_balance(target_user_id, amount) # Refund
    await callback.message.edit_text(text=callback.message.text + f"\n\n❌ REJECTED (Refunded {amount} ETB)")
    try:
        await bot.send_message(target_user_id, f"❌ የገንዘብ ማውጫ ጥያቄዎ ውድቅ ተደርጓል። {amount} ETB ወደ ቀሪ ሂሳብዎ ተመልሷል።")
    except Exception:
        pass

# --- Admin Section Handlers ---

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    await message.answer("👑 እንኳን ወደ Admin Control Panel በደህና መጡ", reply_markup=get_admin_menu())

@dp.message(F.text == "📢 Broadcast Message")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_ID:
        return
    await message.answer("እባክዎ ለሁሉም ተጠቃሚዎች የሚተላለፈውን መልዕክት ይጻፉ፡")
    await state.set_state(UserStates.waiting_for_broadcast_msg)

@dp.message(UserStates.waiting_for_broadcast_msg)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_ID:
        return
    await state.clear()
    
    # Simple broadcast to all registered users (In real production, query DB all users)
    # Since SQLite connection helper query is simplified, let's connect directly
    import aiosqlite
    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            
    sent_count = 0
    await message.answer("📢 መልዕክት ማስተላለፍ ተጀምሯል...")
    for row in rows:
        try:
            await bot.send_message(chat_id=row[0], text=message.text)
            sent_count += 1
            await asyncio.sleep(0.05) # Prevent flood limit
        except Exception:
            pass
            
    await message.answer(f"✅ ስርጭቱ ተጠናቋል። ለ {sent_count} ተጠቃሚዎች ተልኳል።")

@dp.message(F.text == "📊 Bot Statistics")
async def show_stats(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    import aiosqlite
    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM withdraw_requests WHERE status = 'PENDING'") as cursor:
            pending_wd = (await cursor.fetchone())[0]
            
    await message.answer(f"📊 **የቦቱ ስታቲስቲክስ**\n\n👥 ጠቅላላ ተጠቃሚዎች፡ {total_users}\n⌛ ያልተከፈሉ Withdraws: {pending_wd}")

@dp.message(F.text == "🔙 Back to Main Menu")
async def back_to_main(message: types.Message):
    await message.answer("ወደ ዋናው ማውጫ ተመልሰዋል፡", reply_markup=get_main_menu())

# --- Main Entry Point ---
async def main():
    await database.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
