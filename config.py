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

    # FXStreet Forex Market News
    FXSTREET_ENABLED = os.environ.get("FXSTREET_ENABLED", "false")
    FXSTREET_CHECK_INTERVAL_MINUTES = int(os.environ.get("FXSTREET_CHECK_INTERVAL_MINUTES", "15"))
    FXSTREET_MIN_SCORE = int(os.environ.get("FXSTREET_MIN_SCORE", "6"))
    FXSTREET_BREAKING_SCORE = int(os.environ.get("FXSTREET_BREAKING_SCORE", "10"))
    FXSTREET_QUEUE_RELEASE_MINUTES = int(os.environ.get("FXSTREET_QUEUE_RELEASE_MINUTES", "30"))
    FXSTREET_TOPIC_COOLDOWN_MINUTES = int(os.environ.get("FXSTREET_TOPIC_COOLDOWN_MINUTES", "120"))
    FXSTREET_QUIET_START = os.environ.get("FXSTREET_QUIET_START", "00:00")
    FXSTREET_QUIET_END = os.environ.get("FXSTREET_QUIET_END", "06:00")
    FXSTREET_SEND_IMAGES = os.environ.get("FXSTREET_SEND_IMAGES", "true")
