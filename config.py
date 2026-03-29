import os
from datetime import timezone, timedelta


class Config:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")
    FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

    CHECK_INTERVAL = 300
    POST_DELAY = 10
    BAGHDAD_TZ = timezone(timedelta(hours=3))

    CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@KurdTraderKRD")  # ✅ زیادکراو
