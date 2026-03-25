import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

# هێنانی کلیلی Groq
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ناساندنی کلاینتی Groq
client_groq = Groq(api_key=GROQ_API_KEY)

async def process_smart_news(title_en):
    try:
        # ١. نمرەدان بە هەواڵەکە (Groq)
        rating_prompt = f"Rate this news importance for Forex traders from 1 to 10: {title_en}. Return ONLY the number."
        rating_resp = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": rating_prompt}]
        )
        
        rating_str = rating_resp.choices[0].message.content.strip()
        rating = int(''.join(filter(str.isdigit, rating_str)) or 0)
        
        logger.info(f"📊 Rating: {rating}/10 for: {title_en[:40]}...")

        if rating >= 6:
            # ٢. وەرگێڕان بە Groq - لێرەدا فەرمانەکەمان توند کردووە بۆ ئەوەی تێبینی نەنووسێت
            translate_prompt = (
                f"Translate this Forex news title into professional Sorani Kurdish: '{title_en}'. "
                "Return ONLY the translated text in Kurdish Arabic script. "
                "Do not include any notes, explanations, or alternative scripts. "
                "Strictly provide the translation only."
            )
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
        # شیکاری ڕۆژانەش بە هەمان شێوەی توند ڕێکدەخەین
        prompt = (
            f"Summarize these Forex news titles into a professional daily report in Sorani Kurdish:\n{all_titles}\n"
            "Return ONLY the Kurdish summary. No notes or English explanations."
        )
        
        analysis_resp = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return analysis_resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Daily analysis error: {e}")
        return None
