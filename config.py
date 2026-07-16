import os
from dotenv import load_dotenv

# .env ፋይልን ለማንበብ
load_dotenv()

# ዋና ሚስጥራዊ ቁልፎች (በኋላ በRender ላይ Environment Variable አድርገን የምናስገባቸው)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7800213349"))

# ተጠቃሚው ግዴታ Join ማድረግ ያለባቸው ቻናሎች ዝርዝር
CHANNELS = [
    "@binance_red_packet12",
    "@hf68ng9hc",
    "@Buzzerfollowbake",
    "@lefegegc"
]

# የሽልማት መጠኖች (በብር/ETB)
REFERRAL_REWARD = 3.0  # ለአንድ ሪፈራል የሚከፈል
TIKTOK_REWARD = 3.0    # ለቲክቶክ ተግባር የሚከፈል

# ዝቅተኛው የማውጫ መጠን (በብር/ETB)
MIN_WITHDRAW = 100.0
