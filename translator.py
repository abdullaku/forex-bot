import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client_groq = Groq(api_key=GROQ_API_KEY)

async def process_smart_news(title_en):
    try:
        # ١. نمرەدان بە هەواڵەکە
        rating_prompt = f"Rate this Forex news importance from 1 to 10: {title_en}. Return ONLY the number."
        rating_resp = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": rating_prompt}]
        )
        rating_str = rating_resp.choices[0].message.content.strip()
        rating = int(''.join(filter(str.isdigit, rating_str)) or 0)
        
        if rating >= 6:
            # ٢. داواکردنی سەردێڕ و کورتەی هەواڵ پێکەوە
            translate_prompt = (
                f"Translate and summarize this Forex news title: '{title_en}'.\n"
                "Format the output exactly like this in Sorani Kurdish (Arabic script):\n"
                "TITLE_HERE\n\nSUMMARY_HERE\n"
                "CRITICAL: Do NOT include English notes, no 'Here is the translation', just the Kurdish text."
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
        
