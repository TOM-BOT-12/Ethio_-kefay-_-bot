import aiosqlite
import os

# በRender ላይ የቋሚ ዲስክ (Persistent Disk) መንገድ ለመጠቀም
# ከሌለ በራሱ 'data' የሚባል ፎልደር ይፈጥራል
DB_DIR = "/data" if os.path.exists("/data") else "data"
DB_PATH = os.path.join(DB_DIR, "users.db")

async def init_db():
    # ፎልደሩ መኖሩን ያረጋግጣል
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # የተጠቃሚዎች መዝገብ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0.0,
                referrals INTEGER DEFAULT 0,
                referred_by INTEGER,
                is_banned INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # የቲክቶክ ተግባራት መቆጣጠሪያ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                user_id INTEGER PRIMARY KEY,
                tiktok_done INTEGER DEFAULT 0,
                task_status TEXT DEFAULT 'not_started' -- 'not_started', 'pending', 'approved', 'rejected'
            )
        """)
        
        # የብር ማውጫ (Withdraw) ጥያቄዎች መዝገብ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                method TEXT,
                account TEXT,
                status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# አዲስ ተጠቃሚ ለመመዝገብ
async def add_user(user_id, username, referred_by=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            if await cursor.fetchone() is None:
                await db.execute(
                    "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
                    (user_id, username, referred_by)
                )
                await db.execute("INSERT OR IGNORE INTO tasks (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return True
        return False

# የተጠቃሚ መረጃ ለማንበብ
async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

# የብር መጠን ለመጨመር ወይም ለመቀነስ
async def update_balance(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

# የሪፈራል ብዛት ለመጨመር
async def increment_referrals(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

# ተጠቃሚን Ban ወይም Unban ለማድረግ
async def set_ban_status(user_id, is_banned):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (is_banned, user_id))
        await db.commit()
