import aiosqlite

DB_PATH = "users.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Create users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0.0,
                referrals INTEGER DEFAULT 0,
                referred_by INTEGER,
                payment_method TEXT,
                payment_details TEXT,
                is_banned INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create withdraw requests table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                method TEXT,
                details TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create tiktok tasks table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                screenshot_file_id TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# --- User Helper Functions ---

async def add_user(user_id: int, username: str, referred_by: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user_id, username, referred_by)
        )
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "user_id": row[0],
                    "username": row[1],
                    "balance": row[2],
                    "referrals": row[3],
                    "referred_by": row[4],
                    "payment_method": row[5],
                    "payment_details": row[6],
                    "is_banned": row[7],
                    "joined_at": row[8]
                }
            return None

async def update_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def increment_referrals(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

async def set_payment_info(user_id: int, method: str, details: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET payment_method = ?, payment_details = ? WHERE user_id = ?",
            (method, details, user_id)
        )
        await db.commit()

async def set_ban_status(user_id: int, status: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (status, user_id)
        )
        await db.commit()

# --- Withdraw Helper Functions ---

async def create_withdraw_request(user_id: int, amount: float, method: str, details: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO withdraw_requests (user_id, amount, method, details) VALUES (?, ?, ?, ?)",
            (user_id, amount, method, details)
        )
        await db.commit()

# --- TikTok Helper Functions ---

async def submit_tiktok_task(user_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO tiktok_tasks (user_id, screenshot_file_id) VALUES (?, ?)",
            (user_id, file_id)
        )
        await db.commit()
