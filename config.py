
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Force Join Channels
CHANNELS = [
    "@binance_red_packet12",
    "@hf68ng9hc",
    "@Buzzerfollowbake",
    "@lefegegc"
]

# Reward Settings
REFERRAL_REWARD = 3  # ETB
TIKTOK_REWARD = 3   # ETB

# Withdraw Settings
MIN_WITHDRAW = 100  # ETB
