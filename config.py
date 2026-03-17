import os

class Config:
    # ئەمانە وەک خۆیان بن
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8611761761:AAEU_XJjV8QQ3LPr2rWf6gDBNnH2TVbs3_E")
    CHANNEL_ID = os.getenv("CHANNEL_ID", "-1003829360084")
    
    # ئەم دێڕەی خوارەوەمان گۆڕی بۆ GEMINI_API_KEY چونکە فایلەکانی تر داوای ئەم ناوە دەکەن
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "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")
    
    # ئەمانەش وەک خۆیان بن
    CHECK_INTERVAL_SECONDS = 900
    POST_DELAY_SECONDS = 180
    TRANSLATE_DELAY_SECONDS = 5
    MAX_POSTS_PER_DAY = 20

