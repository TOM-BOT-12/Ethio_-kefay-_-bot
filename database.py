
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

CHANNELS = [
    "@binance_red_packet12",
    "@hf68ng9hc",
    "@Buzzerfollowbake",
    "@lefegegc"
]

REFERRAL_REWARD = 3
TIKTOK_REWARD = 3

MIN_WITHDRAW = 100
