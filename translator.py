import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


async def process_smart_news(title, description=""):
    try:
        # 🔹 1. Rating
        rating_prompt = f"Rate this Forex news from 1 to 10: {title}. فقط رقم."

        rating_resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": rating_prompt}]
        )

        rating_text = rating_resp.choices[0].message.content.strip()
        rating = int(''.join(filter(str.isdigit, rating_text)) or 0)

        logger.info(f"Rating: {rating}")

        # 🔻 فلتر
        if rating < 6:
            return None

        # 🔹 2. Translation
        content = f"{title}\n{description}"

        prompt = (
            f"Translate and summarize this Forex news into Kurdish (Sorani):\n"
            f"{content}\n\n"
            f"Give:\n"
            f"- Strong Kurdish title\n"
            f"- Short summary\n"
            f"Only Kurdish."
        )

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        return resp.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Translator error: {e}")
        return None
