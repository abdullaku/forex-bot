import os
from datetime import timezone, timedelta


class Config:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    SUPPORT_TOKEN = os.environ.get("SUPPORT_TOKEN")  # ✅ توکێنی @KurdTraderSupport_bot
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")
    FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

    CHECK_INTERVAL = 30   # هەر 30 چرکە — ETag بوونی هەیە بۆیە سەرباری زیادە نییە
    POST_DELAY = 3    # 3 چرکە نێوان پۆستەکان
    BAGHDAD_TZ = timezone(timedelta(hours=3))

    CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@KurdTraderKRD")

    # ── DinarAPI ──────────────────────────────────────────────────────────────
    DINAR_API_TOKEN = os.environ.get("DINAR_API_TOKEN", "")
