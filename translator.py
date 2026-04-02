import os
import re
import asyncio
import logging
from groq import Groq
from google import genai

logger = logging.getLogger(__name__)


class TranslatorConfig:
    API_KEY = os.getenv("GROQ_API_KEY")
    MODEL = "llama-3.3-70b-versatile"

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = "gemini-2.5-flash"

    @classmethod
    def validate(cls):
        if not cls.API_KEY:
            raise ValueError("❌ GROQ_API_KEY is not set in environment variables")
        if not cls.GEMINI_API_KEY:
            raise ValueError("❌ GEMINI_API_KEY is not set in environment variables")


TranslatorConfig.validate()


class SmartTranslator:
    def __init__(self):
        self.client = Groq(api_key=TranslatorConfig.API_KEY)
        self.model = TranslatorConfig.MODEL

        self.gemini_client = genai.Client(api_key=TranslatorConfig.GEMINI_API_KEY)
        self.gemini_model = TranslatorConfig.GEMINI_MODEL

        self.forbidden_script_pattern = re.compile(
            r"[\u0400-\u04FF"
            r"\u3040-\u30FF"
            r"\u0900-\u097F"
            r"\u0E00-\u0E7F"
            r"\u4E00-\u9FFF]"
        )

        self.allowed_punctuation_pattern = re.compile(
            r"[^0-9A-Za-z\u0600-\u06FF\s\.,:%$€£()\-\/'\":؛،؟!+]"
        )

    def _create_prompt(self, title: str, description: str = "", strict: bool = False) -> str:
        content = f"{title}\n{description}".strip()

        strict_block = ""
        if strict:
            strict_block = (
                "\nIMPORTANT RETRY RULES:\n"
                "- Your previous answer contained mixed or foreign script.\n"
                "- This time output ONLY Sorani Kurdish in Arabic script.\n"
                "- Never output Cyrillic, Japanese, Hindi, Turkish, Kurmanji, or any foreign letters.\n"
                "- Keep only true English proper nouns exactly as they are.\n"
                "- If a word is not a proper noun, translate it into Sorani Kurdish.\n"
            )

        return (
            "You are a senior financial news editor for a Kurdish trading channel.\n\n"
            "Read the news below carefully and decide if it is directly relevant to Forex traders.\n\n"
            "If NOT relevant → reply only: SKIP\n\n"
            "If relevant → write a short Kurdish post (Sorani).\n\n"
            f"{strict_block}\n"
            f"News:\n{content}"
        )

    def _clean_result(self, text: str) -> str:
        text = self.forbidden_script_pattern.sub(" ", text)
        text = self.allowed_punctuation_pattern.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _chat_sync(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    async def _chat(self, prompt: str) -> str:
        return await asyncio.to_thread(self._chat_sync, prompt)

    # ✅ GEMINI FINAL STYLE (UPDATED)
    def _gemini_translate_sync(self, text: str) -> str:
        prompt = (
            "Rewrite the following financial and forex news text into clear, natural, professional Central Kurdish (Sorani) "
            "for a Kurdish Telegram news channel.\n\n"

            "Language rules:\n"
            "- Write only in Central Kurdish (Sorani) using Arabic script.\n"
            "- Use fluent, natural Sorani.\n"
            "- Avoid awkward or literal translation.\n\n"

            "Style rules:\n"
            "- No emojis.\n"
            "- No hype.\n"
            "- Keep it clean and professional.\n\n"

            "Structure:\n"
            "1. Short headline\n"
            "2. Main news\n"
            "3. Market implication\n\n"

            "Important:\n"
            "- Keep terms like Fed, USD, IMF, Brent in English.\n"
            "- Do not add extra text.\n"
            "- Output only final Kurdish text.\n\n"

            f"Text:\n{text}"
        )

        response = self.gemini_client.models.generate_content(
            model=self.gemini_model,
            contents=prompt,
        )
        return (response.text or "").strip()

    async def _gemini_translate(self, text: str) -> str:
        return await asyncio.to_thread(self._gemini_translate_sync, text)

    async def process(self, title: str, description: str = ""):
        try:
            prompt = self._create_prompt(title, description)
            result = await self._chat(prompt)

            if "SKIP" in result.upper():
                logger.info(f"⏭️ Skipped: {title[:60]}")
                return None

            cleaned = self._clean_result(result)

            if not cleaned or len(cleaned) < 10:
                return None

            # delay before Gemini
            await asyncio.sleep(5)

            try:
                gemini_result = await self._gemini_translate(cleaned)
                if gemini_result and len(gemini_result) > 10:
                    cleaned = gemini_result
            except Exception as e:
                logger.warning(f"Gemini error: {e}")

            logger.info(f"✅ Translated: {title[:60]}")
            return cleaned

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(title: str, description: str = ""):
    return await _translator.process(title, description)
