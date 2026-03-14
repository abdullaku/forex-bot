import os

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8611761761:AAEU_XJjV8QQ3LPr2rWf6gDBNnH2TVbs3_E")
    CHANNEL_ID = os.getenv("CHANNEL_ID", "@Economic_news_Kurdish")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDiLR-mTpcgqPyWgry2eZM9AJCoXODLDao")
    CHECK_INTERVAL_SECONDS = 1800
    POST_DELAY_SECONDS = 5
    MAX_POSTS_PER_DAY = 20
