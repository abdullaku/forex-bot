import os
from datetime import timezone, timedelta


class Config:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    SUPPORT_TOKEN = os.environ.get("SUPPORT_TOKEN")  # ✅ توکێنی @KurdTraderSupport_bot
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")
    FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

    CHECK_INTERVAL = 300
    POST_DELAY = 10
    BAGHDAD_TZ = timezone(timedelta(hours=3))

    CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@KurdTraderKRD")

    # ── DinarAPI ──────────────────────────────────────────────────────────────
    DINAR_API_TOKEN = os.environ.get("DINAR_API_TOKEN", "")

    # ── Feature flags ─────────────────────────────────────────────────────────
    ENABLE_SUPPORT_BOT = os.environ.get("ENABLE_SUPPORT_BOT", "true").lower() == "true"
    ENABLE_NEWS_LOOP = os.environ.get("ENABLE_NEWS_LOOP", "true").lower() == "true"
    ENABLE_PRICE_POSTER = os.environ.get("ENABLE_PRICE_POSTER", "true").lower() == "true"
    ENABLE_DINAR_POSTER = os.environ.get("ENABLE_DINAR_POSTER", "true").lower() == "true"
