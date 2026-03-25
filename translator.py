import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client_groq = Groq(api_key=GROQ_API_KEY)

# لێرە دەبێت 'description'یش وەربگرێت بۆ ئەوەی بتوانێت کورتەی بکات
async def process_smart_news(title_en, description_en=""):
    try:
        # ١. نمرەدان بە هەواڵەکە بەپێی ناونیشانەکە
        rating_prompt = f"Rate this Forex news importance from 1 to 10: {title_en}. Return ONLY the number."
        rating_resp = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": rating_prompt}]
        )
        rating_str = rating_resp.choices[0].message.content.strip()
        rating = int(''.join(filter(str.isdigit, rating_str)) or 0)
        
        if rating >= 6:
            # ٢. دروستکردنی سەردێڕ و کورتە بە کوردی
            # ئەگەر کورتەی هەواڵەکە هەبوو بەکاری دەهێنێت، ئەگەر نا هەر لە ناونیشانەکە دروستی دەکات
            content_to_process = f"Title: {title_en}\nDetails: {description_en}" if description_en else title_en
            
            translate_prompt = (
                f"Based on this news: '{content_to_process}', provide:\n"
                "1. A strong Kurdish title (Sorani).\n"
                "2. A professional Kurdish summary (Sorani) explaining the impact on the market.\n\n"
                "Format: TITLE\n\nSUMMARY\n"
                "Strictly Kurdish, no English intro."
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
        
