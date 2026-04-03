import os
import re
import asyncio
import logging
from groq import Groq

logger = logging.getLogger(__name__)


class TranslatorConfig:
    API_KEY = os.getenv("GROQ_API_KEY")
    MODEL = "llama-3.3-70b-versatile"

    @classmethod
    def validate(cls):
        if not cls.API_KEY:
            raise ValueError("❌ GROQ_API_KEY is not set in environment variables")


TranslatorConfig.validate()


class SmartTranslator:
    def __init__(self):
        self.client = Groq(api_key=TranslatorConfig.API_KEY)
        self.model = TranslatorConfig.MODEL

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

    def _create_filter_prompt(self, title: str, description: str = "") -> str:
        content = f"{title}\n{description}".strip()
        return (
            "You are a senior financial news editor for a Kurdish trading channel.\n\n"
            "Read the news below carefully and decide if it is directly relevant to Forex traders.\n\n"
            "If NOT relevant → reply only: SKIP\n\n"
            "If relevant → reply only: YES\n\n"
            f"News:\n{content}"
        )

    def _create_translate_prompt(self, title: str, description: str = "") -> str:
        content = f"{title}\n{description}".strip()
        return (
            "Rewrite the following financial and forex news text into clear, natural, professional Central Kurdish (Sorani) "
            "for a Kurdish Telegram news channel.\n\n"

            "Thinking rules:\n"
            "- Understand the news deeply before writing.\n"
            "- Rewrite it as a financial analyst would explain it.\n"
            "- Do NOT translate word-by-word.\n"
            "- Make the meaning clear even if the original text is complex or awkward.\n"
            "- If the original text is unclear, rewrite it into clear and meaningful Kurdish.\n\n"

            "Accuracy rules:\n"
            "- Preserve the exact meaning and core facts.\n"
            "- Do NOT change the main topic.\n"
            "- Do NOT replace countries, assets, or causes with different ones.\n"
            "- If the news is about gas, do not change it to oil.\n"
            "- If a country is mentioned, keep it.\n"
            "- Keep numbers and percentages accurate.\n"
            "- Do not invent background details.\n\n"

            "Language rules:\n"
            "- Write only in Central Kurdish (Sorani) using Arabic script.\n"
            "- Use fluent, natural Sorani.\n"
            "- Avoid awkward, literal, or machine-like translation.\n"
            "- Use clear journalistic Kurdish.\n"
            "- Avoid vague wording when a clearer financial wording exists.\n\n"

            "Terminology rules:\n"
            "- Use precise financial and market terminology.\n"
            "- Preserve important financial terms when needed, such as hedge fund, bond, yield, private credit.\n"
            "- Do not over-generalize financial entities.\n"
            "- If a technical term is better kept in English, keep it naturally inside the Kurdish sentence.\n\n"

            "Style rules:\n"
            "- No emojis.\n"
            "- No hype.\n"
            "- No dramatic or exaggerated tone.\n"
            "- Keep it clean, readable, and professional.\n"
            "- Make it suitable for a Forex and financial Telegram channel.\n\n"

            "Structure:\n"
            "- First line: a short, strong, market-focused headline that shows direction or impact, not a generic title.\n"
            "- Second paragraph: the main news in 1 or 2 clear sentences.\n"
            "- Third paragraph: one short sentence showing the likely market implication.\n\n"

            "Important:\n"
            "- Keep terms like Fed, USD, IMF, Brent, WTI, CPI, GDP in English when needed.\n"
            "- Do not add extra information outside the scope of the news.\n"
            "- Output only final Kurdish text.\n\n"

            f"Text:\n{content}"
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

    async def process(self, title: str, description: str = ""):
        try:
            # Step 1: Filter
            filter_prompt = self._create_filter_prompt(title, description)
            filter_result = await self._chat(filter_prompt)

            if "SKIP" in filter_result.upper():
                logger.info(f"⏭️ Skipped: {title[:60]}")
                return None

            await asyncio.sleep(2)

            # Step 2: Translate with full Gemini-style prompt
            translate_prompt = self._create_translate_prompt(title, description)
            translated = await self._chat(translate_prompt)

            cleaned = self._clean_result(translated)

            if not cleaned or len(cleaned) < 10:
                return None

            logger.info(f"✅ Translated: {title[:60]}")
            return cleaned

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(title: str, description: str = ""):
    return await _translator.process(title, description)
