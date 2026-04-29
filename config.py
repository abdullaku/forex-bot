import os
from datetime import timezone, timedelta


class Config:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    SUPPORT_TOKEN = os.environ.get("SUPPORT_TOKEN")
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")
    FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

    CHECK_INTERVAL = 30
    POST_DELAY = 3
    BAGHDAD_TZ = timezone(timedelta(hours=3))

    CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@KurdTraderKRD")

    DINAR_API_TOKEN = os.environ.get("DINAR_API_TOKEN", "")

    # Economic Calendar - ForexFactory only
    CALENDAR_PROVIDER = os.environ.get("CALENDAR_PROVIDER", "forexfactory")
    DAILY_CALENDAR_FETCH_TIME = os.environ.get("DAILY_CALENDAR_FETCH_TIME", "08:55")
    DAILY_CALENDAR_POST_TIME = os.environ.get("DAILY_CALENDAR_POST_TIME", "09:00")
    PRE_ALERT_MINUTES = int(os.environ.get("PRE_ALERT_MINUTES", "30"))
    RESULT_POLL_SECONDS = int(os.environ.get("RESULT_POLL_SECONDS", "60"))
    RESULT_POLL_WINDOW_MINUTES = int(os.environ.get("RESULT_POLL_WINDOW_MINUTES", "15"))
    CALENDAR_REFRESH_NORMAL_MINUTES = int(os.environ.get("CALENDAR_REFRESH_NORMAL_MINUTES", "360"))
