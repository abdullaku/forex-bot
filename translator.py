import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


async def process_smart_news(title):
    try:
        prompt = (
            f"Translate this Forex news into Kurdish (Sorani) with strong title and short summary:\n{title}"
        )

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        return resp.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Translator error: {e}")
        return None
