import os
import asyncio
import logging
import re
from groq import Groq

logger = logging.getLogger(__name__)


class TranslatorConfig:
    API_KEY = os.getenv("GROQ_API_KEY")
    MODEL = "llama-3.3-70b-versatile"
    MIN_RATING = 6

    @classmethod
    def validate(cls):
        if not cls.API_KEY:
            raise ValueError("❌ GROQ_API_KEY is not set in environment variables")


TranslatorConfig.validate()


class SmartTranslator:
    def __init__(self):
        self.client = Groq(api_key=TranslatorConfig.API_KEY)
        self.model = TranslatorConfig.MODEL
        self.min_rating = TranslatorConfig.MIN_RATING

    def _create_rating_prompt(self, title: str) -> str:
        return (
            f"Rate this Forex news from 1 to 10: {title}. "
            f"Return only one number."
        )

    def _create_translation_prompt(self, title: str, description: str = "") -> str:
        content = f"{title}\n{description}".strip()

        return (
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

    def _extract_rating(self, text: str) -> int:
        # ✅ تەنها ژمارەی یەکەم دەگرێت — "7 out of 10" → 7، نەک 710
        match = re.search(r'\d+', text)
        return int(match.group()) if match else 0

    def _clean_result(self, text: str) -> str:
        text = text.replace("**", "")
        text = text.replace("__", "")
        text = text.replace("```", "")
        text = text.replace("##", "")
        text = text.replace("*", "")
        return text.strip()

    def _chat_sync(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

    async def _chat(self, prompt: str) -> str:
        # ✅ sync کۆد لە thread جیاوازدا دەکات — event loop بلۆک نابێت
        return await asyncio.to_thread(self._chat_sync, prompt)

    async def process(self, title: str, description: str = ""):
        try:
            rating_prompt = self._create_rating_prompt(title)
            rating_text = await self._chat(rating_prompt)
            rating = self._extract_rating(rating_text)

            logger.info(f"Rating: {rating}")

            if rating < self.min_rating:
                return None

            translation_prompt = self._create_translation_prompt(title, description)
            result = await self._chat(translation_prompt)

            return self._clean_result(result)

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(title, description=""):
    return await _translator.process(title, description)
