import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_ID
from database import init_db, add_user, get_user

# ሎግ ለመቆጣጠር
logging.basicConfig(level=logging.INFO)

# 1. FastAPI ዌብ ሰርቨር ማዋቀር (Render እንዳይተኛ ለመከላከል)
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "running", "bot": "Ethio Kefay Rewards Bot is active!"}

# 2. የቴሌግራም ቦት ማዋቀር
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# የመጀመርያ መልዕክት (Welcome message)
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
    
    # የሪፈራል ሊንክ መኖሩን ማረጋገጥ (ለምሳሌ /start 12345678)
    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].isdigit():
        referred_by = int(args[1])
        if referred_by == user_id:
            referred_by = None  # ራሱን መጋበዝ አይችልም
            
    # ተጠቃሚውን መመዝገብ
    is_new = await add_user(user_id, username, referred_by)
    
    # ሪፈራል ካለውና አዲስ ተጠቃሚ ከሆነ ብቻ ለጋባዡ ሪፈራል እንጨምራለን
    # ማስታወሻ፡ እውነተኛውን የብር አከፋፈል እና ቻናል መቆጣጠሪያ በቀጣይ ክፍሎች እንጨምረዋለን
    
    await message.answer(WELCOME_TEXT)

# ቦቱን እና ዌብ ሰርቨሩን በአንድ ላይ ለማስኬድ
async def run_bot():
    await init_db()
    await dp.start_polling(bot)

# ሰርቨሩ ሲነሳ ቦቱንም አብሮ እንዲያስነሳ
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    # Render የሚሰጠውን ፖርት ፈልጎ ያነባል
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
