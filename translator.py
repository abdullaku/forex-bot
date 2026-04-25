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
    """
    AI is used only for Kurdish formatting and market explanation.
    It does NOT decide whether to skip the news.
    Filtering must happen only at the source level in news.py.
    """

    def __init__(self):
        self.client = Groq(api_key=TranslatorConfig.API_KEY)
        self.model = TranslatorConfig.MODEL

        self.forbidden_script_pattern = re.compile(
            r"[\u0400-\u04FF"
            r"\u3040-\u30FF"
            r"\u0900-\u097F"
            r"\u0E00-\u9FFF]"
        )

        self.allowed_inline_pattern = re.compile(
            r"[^0-9A-Za-z\u0600-\u06FF\s\.\,\:\%\$\€\£\(\)\-\/\'\"\؛\،\؟\!\+\•]"
        )

    def _create_translate_prompt(
        self,
        title: str,
        description: str = "",
        source: str = "",
        currency: str = "",
    ) -> str:
        content = f"{title}\n{description}".strip()

        return (
            "You are a professional Kurdish macro Forex news writer for a Telegram channel.\n\n"

            "Important rule:\n"
            "- Do NOT decide whether this news should be skipped.\n"
            "- The source has already been approved as an official macro source.\n"
            "- Your job is only to rewrite, summarize, and format the news in Sorani Kurdish.\n\n"

            "Source context:\n"
            f"- Source: {source or 'Official source'}\n"
            f"- Currency: {currency or 'Unknown'}\n\n"

            "Writing rules:\n"
            "- Write in natural Central Kurdish Sorani using Arabic script.\n"
            "- Keep official names like Fed, BLS, BEA, ECB, Eurostat, BoE, ONS, BoJ, USD, EUR, GBP, JPY, CPI, GDP, PCE, NFP in English when useful.\n"
            "- Keep all numbers, dates, percentages, and official facts accurate.\n"
            "- Do NOT invent actual, forecast, previous, or market reaction if not provided.\n"
            "- Do NOT create trading signals.\n"
            "- Do NOT say BUY or SELL.\n"
            "- Do NOT use clickbait.\n"
            "- Do NOT output explanations outside the final post.\n"
            "- Do NOT use markdown like ** or ##.\n\n"

            "Output format exactly:\n"
            "Line 1: [emoji] short official headline in Kurdish\n"
            "Line 2: blank line\n"
            "Line 3: 📰 هەواڵ:\n"
            "Line 4: one short paragraph explaining the official news\n"
            "Line 5: blank line\n"
            "Line 6: 📌 گرنگی بۆ Forex:\n"
            "Line 7: explain briefly why this matters for the related currency and major Forex markets\n"
            "Line 8: blank line\n"
            "Line 9: ⚠️ تێبینی:\n"
            "Line 10: ئەمە signal نییە؛ تەنها شیکاری هەواڵی ڕەسمییە.\n\n"

            "Return only the final formatted Kurdish post body.\n\n"

            f"Official news:\n{content}"
        )

    def _clean_line(self, line: str) -> str:
        line = self.forbidden_script_pattern.sub(" ", line)
        line = self.allowed_inline_pattern.sub(" ", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        return line

    def _clean_result(self, text: str) -> str:
        if not text:
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        raw_lines = text.split("\n")

        cleaned_lines = []
        blank_pending = False

        for raw in raw_lines:
            line = self._clean_line(raw)

            if not line:
                if cleaned_lines:
                    blank_pending = True
                continue

            if blank_pending and cleaned_lines:
                cleaned_lines.append("")
                blank_pending = False

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def _chat_sync(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.35,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    async def _chat(self, prompt: str) -> str:
        return await asyncio.to_thread(self._chat_sync, prompt)

    async def process(
        self,
        title: str,
        description: str = "",
        source: str = "",
        currency: str = "",
    ):
        try:
            translate_prompt = self._create_translate_prompt(
                title=title,
                description=description,
                source=source,
                currency=currency,
            )

            translated = await self._chat(translate_prompt)
            cleaned = self._clean_result(translated)

            if not cleaned or len(cleaned) < 20:
                logger.warning(f"⚠️ Empty AI formatting result: {title[:60]}")
                return None

            logger.info(f"✅ Formatted official news: {title[:60]}")
            return cleaned

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(
    title: str,
    description: str = "",
    source: str = "",
    currency: str = "",
):
    return await _translator.process(
        title=title,
        description=description,
        source=source,
        currency=currency,
    )
