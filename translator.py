import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

# هێنانی کلیلی Groq لە ڕێگەی ژینگەی Render
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ناساندنی کلاینتی Groq (تەنها ئەمە بەکاردەهێنین بۆ ئەوەی تووشی سنووردارکردن نەبین)
client_groq = Groq(api_key=GROQ_API_KEY)

async def process_smart_news(title_en):
    try:
        # ١. نمرەدان بە هەواڵەکە لە ڕێگەی Groq (Llama 3.3 70B)
        rating_prompt = f"Rate this news importance for Forex traders from 1 to 10: {title_en}. Return ONLY the number."
        rating_resp = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": rating_prompt}]
        )
        
        rating_str = rating_resp.choices[0].message.content.strip()
        rating = int(''.join(filter(str.isdigit, rating_str)) or 0)
        
        logger.info(f"📊 Rating: {rating}/10 for: {title_en[:40]}...")

        # ئەگەر نمرەکە ٦ یان زیاتر بوو، وەرگێڕانی بۆ دەکەین
        if rating >= 6:
            # ٢. وەرگێڕان بە Groq لەجیاتی Gemini بۆ دوورکەوتنەوە لە Error 429
            translate_prompt = f"Translate this Forex news into professional Sorani Kurdish: {title_en}"
            translate_resp = client_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": translate_prompt}]
            )
            return translate_resp.choices[0].message.content.strip()
            
        return None
    except Exception as e:
        logger.error(f"❌ Error in translator: {e}")
        return None

async def generate_daily_analysis(articles):
    try:
        all_titles = "\n".join([a['title'] for a in articles])
        prompt = f"Summarize these Forex news titles into a professional daily report in Sorani Kurdish:\n{all_titles}"
        
        # ئەنجامدانی شیکاری ڕۆژانە بە Groq
        analysis_resp = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return analysis_resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Daily analysis error: {e}")
        return None
        
