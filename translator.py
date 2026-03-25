import logging
from google import genai
from groq import Groq
from config import Config

logger = logging.getLogger(__name__)

# ناساندنی کلاینتەکان بە بەکارهێنانی کلیلەکانی ناو Config
client_gemini = genai.Client(api_key=Config.GEMINI_API_KEY)
client_groq = Groq(api_key=Config.GROQ_API_KEY)

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

        # ٢. ئەگەر نمرەکە ٦ یان زیاتر بوو، وەرگێڕان بە Gemini 2.0 Flash
        if rating >= 6:
            translate_prompt = f"Translate this Forex news into professional Sorani Kurdish: {title_en}"
            response = client_gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=translate_prompt
            )
            return response.text.strip()
            
        return None
    except Exception as e:
        logger.error(f"❌ Error in translator: {e}")
        return None

async def generate_daily_analysis(articles):
    """دروستکردنی شیکاری ڕۆژانە"""
    try:
        all_titles = "\n".join([a['title'] for a in articles])
        prompt = f"Summarize these Forex news titles into a professional daily report in Sorani Kurdish:\n{all_titles}"
        response = client_gemini.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Daily analysis error: {e}")
        return None
        
