import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


async def process_smart_news(title, description=""):
    try:
        # 🔹 1. Rating
        rating_prompt = (
            f"Rate this Forex news from 1 to 10: {title}. "
            f"Return only one number."
        )

        rating_resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": rating_prompt}]
        )

        rating_text = rating_resp.choices[0].message.content.strip()
        rating = int(''.join(filter(str.isdigit, rating_text)) or 0)

        logger.info(f"Rating: {rating}")

        # 🔻 Filter
        if rating < 6:
            return None

        # 🔹 2. Translation
        content = f"{title}\n{description}".strip()

        prompt = (
            "Translate and summarize this Forex news into Kurdish Sorani.\n\n"
            f"News:\n{content}\n\n"
            "Instructions:\n"
            "1. Write one strong Kurdish title.\n"
            "2. Write one short Kurdish summary.\n"
            "3. Kurdish Sorani only.\n"
            "4. No English.\n"
            "5. No markdown.\n"
            "6. Do not use ** or * or bullets or hashtags.\n"
            "7. Plain clean text only.\n"
            "8. Output format must be:\n"
            "TITLE\n\nSUMMARY"
        )

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        result = resp.choices[0].message.content.strip()

        # پاککردنەوەی زیادە بۆ ئەگەر markdown هات
        result = result.replace("**", "")
        result = result.replace("__", "")
        result = result.replace("```", "")
        result = result.replace("##", "")
        result = result.replace("*", "")

        return result.strip()

    except Exception as e:
        logger.error(f"Translator error: {e}")
        return None
